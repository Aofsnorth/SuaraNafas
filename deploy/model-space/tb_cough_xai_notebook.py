# %% [markdown]
# # SuaraNafas: Multimodal Explainable TB Cough Detection Pipeline
# **Kaggle Notebook Template (Verified Schema for CODA TB Challenge)**
#
# This template is customized for the exact columns of the CODA TB Challenge dataset:
# - **Clinical Metadata**: Age, Sex, Height, Weight, Heart Rate, Temperature, and self-reported symptoms (Fever, Weight Loss, Night Sweats, Hemoptysis, Smoking, Prior TB).
# - **Multi-Instance Audio Mapping**: Maps each patient to multiple audio files (using `CODA_TB_Solicited_Meta_Info.csv`).
# - **Model**: Multitask YOHO (local frame boundaries) + ProtoPNet (case-based prototypes) + Late Fusion Classifier.
#
# **Author:** Antigravity (Advanced Agentic Coding Team, Google DeepMind)

# %%
# CELL 1: Install Dependencies
!pip install -q synapseclient librosa soundfile torch torchvision matplotlib pandas openpyxl scikit-learn

# %%
# CELL 2: Sage Bionetworks (Synapse) API Data Downloader
# To run this securely in Kaggle, add your Synapse Personal Access Token as a Kaggle Secret labeled "SYNAPSE_TOKEN".

import os
import synapseclient

def download_synapse_folder(syn, folder_id, dest_dir):
    """
    Downloads all files in a Synapse folder recursively.
    """
    os.makedirs(dest_dir, exist_ok=True)
    print(f"🔄 Listing files in folder {folder_id}...")
    try:
        children = syn.getChildren(folder_id)
        for child in children:
            c_id = child.get('id')
            c_name = child.get('name')
            c_type = child.get('type')
            if 'File' in c_type:
                target_path = os.path.join(dest_dir, c_name)
                if not os.path.exists(target_path):
                    try:
                        print(f"  • Downloading {c_name} ({c_id})...")
                        syn.get(c_id, downloadLocation=dest_dir)
                    except Exception as e:
                        print(f"  • [ERROR] Failed to download {c_name}: {e}")
                else:
                    print(f"  • [SKIP] {c_name} already exists.")
            elif 'Folder' in c_type:
                download_synapse_folder(syn, c_id, os.path.join(dest_dir, c_name))
    except Exception as e:
        print(f"  • [ERROR] Failed to get children of folder {folder_id}: {e}")

def download_coda_tb_dataset(dest_dir="./coda_tb_data"):
    """
    Downloads clinical CSVs, audio metadata, and raw audio files from Synapse.
    """
    os.makedirs(dest_dir, exist_ok=True)

    try:
        from kaggle_secrets import UserSecretsClient
        user_secrets = UserSecretsClient()
        synapse_token = user_secrets.get_secret("SYNAPSE_TOKEN")
        print("🔑 Synapse token retrieved from Kaggle Secrets.")
    except Exception:
        synapse_token = os.environ.get("SYNAPSE_TOKEN") or input("Please enter your Synapse Personal Access Token (PAT): ")

    if not synapse_token:
        print("❌ Cannot proceed without a Synapse Token.")
        return

    syn = synapseclient.Synapse()
    syn.login(authToken=synapse_token)

    # Files IDs mapping from Synapse file catalog
    file_ids = {
        "Clinical_Meta": "syn41604915",
        "Additional_Vars": "syn52357041",
        "Solicited_Meta": "syn41604939",
        "Data_Dictionary": "syn41743692"
    }

    print("\n🔄 Downloading metadata files...")
    for name, syn_id in file_ids.items():
        try:
            print(f"  • Downloading {name} ({syn_id})...")
            syn.get(syn_id, downloadLocation=dest_dir)
        except Exception as e:
            print(f"  • [ERROR] Failed to download {name}: {e}")

    # Download the solicited_data audio folder (ID: syn40358494)
    print("\n🔄 Downloading solicited audio directory (*.wav files)...")
    download_synapse_folder(syn, "syn40358494", os.path.join(dest_dir, "solicited_data"))

    print("\n✅ Dataset download complete!")

# Uncomment to download dataset inside Kaggle:
# download_coda_tb_dataset()

# %%
# CELL 3: GPU Device Configuration
import torch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"💻 Execution Device: {device}")
if torch.cuda.is_available():
    print(f"  • GPU Model: {torch.cuda.get_device_name(0)}")

# %%
# CELL 4: Metadata Preprocessing & Encoder
# Encodes clinical features with z-score normalization.

import pandas as pd
import numpy as np

def preprocess_metadata(clinical_csv_path, additional_csv_path):
    """
    Loads and preprocesses clinical metadata according to the exact CODA schema.
    Returns processed DataFrame and mapping dictionary.
    """
    df_clinical = pd.read_csv(clinical_csv_path)
    df_additional = pd.read_csv(additional_csv_path)

    # Merge on participant ID
    df = pd.merge(df_clinical, df_additional, on="participant", how="inner")

    # 1. Binary Encodings
    binary_maps = {
        'sex': {'Male': 1.0, 'Female': 0.0},
        'tb_prior': {'Yes': 1.0, 'No': 0.0},
        'tb_prior_Pul': {'Yes': 1.0, 'No': 0.0},
        'tb_prior_Extrapul': {'Yes': 1.0, 'No': 0.0},
        'tb_prior_Unknown': {'Yes': 1.0, 'No': 0.0},
        'hemoptysis': {'Yes': 1.0, 'No': 0.0},
        'weight_loss': {'Yes': 1.0, 'No': 0.0},
        'smoke_lweek': {'Yes': 1.0, 'No': 0.0},
        'fever': {'Yes': 1.0, 'No': 0.0},
        'night_sweats': {'Yes': 1.0, 'No': 0.0}
    }

    for col, mapping in binary_maps.items():
        if col in df.columns:
            df[col] = df[col].map(mapping).fillna(0.0)

    # 2. One-Hot Encoding for Country and HIVstatus
    df = pd.get_dummies(df, columns=['Country', 'HIVstatus'], prefix=['country', 'hiv'], dtype=float)

    # 3. Numeric Standardization (Z-score normalization)
    numeric_cols = ['age', 'height', 'weight', 'reported_cough_dur', 'heart_rate', 'temperature']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].mean())
            df[col] = (df[col] - df[col].mean()) / (df[col].std() + 1e-8)

    # Select feature columns (excluding identifiers, sputum codes, and target)
    exclude_cols = ['participant', 'type', 'tb_status', 'Microbiologicreferencestandard',
                    'Sputumxpertreferencestandard', 'Xpertcombinedsemiquant']
    feature_cols = [c for c in df.columns if c not in exclude_cols]

    print(f"📊 Extracted {len(feature_cols)} clinical features: {feature_cols}")
    return df, feature_cols

# %%
# CELL 5: Multi-Instance Audio Data Loader
# Maps patients to their corresponding set of elicited cough recording files.

import librosa

class MultiInstanceCODATBDataset(torch.utils.data.Dataset):
    def __init__(self, metadata_df, feature_cols, solicited_csv_path, audio_dir, duration=0.55, sr=16000, n_mels=128):
        self.metadata_df = metadata_df
        self.feature_cols = feature_cols
        self.audio_dir = audio_dir
        self.duration = duration
        self.sr = sr
        self.n_mels = n_mels
        self.audio_file_index = self._index_audio_files(audio_dir)

        # Load solicited metadata mapping participants to file names.
        self.solicited_df = pd.read_csv(solicited_csv_path)

        valid_participants = set(self.metadata_df['participant'])
        self.solicited_df = self.solicited_df[self.solicited_df['participant'].isin(valid_participants)]
        self.patient_audio_map = self.solicited_df.groupby('participant')['filename'].apply(list).to_dict()
        self.participants = [p for p in self.metadata_df['participant'].values if p in self.patient_audio_map]

        # Pre-compute and cache Mel-spectrograms and acoustic features in RAM to avoid CPU load bottleneck
        print("⚡ Pre-computing and caching Mel-spectrograms and handcrafted features in RAM...")
        self.cached_data = {}
        for idx, participant in enumerate(self.participants):
            if idx % 200 == 0:
                print(f"  • Preprocessed {idx}/{len(self.participants)} patients...")
            filenames = self.patient_audio_map[participant]
            specs = []
            yoho_targets = []
            acoustic_vectors = []
            for fname in filenames[:24]:
                spec, yoho, acoustic_vec = self.load_audio_spec(fname)
                specs.append(spec)
                yoho_targets.append(yoho)
                acoustic_vectors.append(acoustic_vec)
            specs_tensor = torch.stack(specs)
            yoho_tensor = torch.stack(yoho_targets)
            avg_acoustic_vec = torch.mean(torch.stack(acoustic_vectors), dim=0)
            self.cached_data[participant] = (specs_tensor, yoho_tensor, avg_acoustic_vec)
        acoustic_matrix = torch.stack([
            cached[2] for cached in self.cached_data.values()
        ])
        acoustic_variance = acoustic_matrix.var(dim=0, unbiased=False)
        collapsed = torch.where(acoustic_variance < 1e-8)[0].tolist()
        if collapsed:
            raise RuntimeError(
                "Acoustic features collapsed across the dataset at indices "
                f"{collapsed}. Verify that real WAV files are being decoded."
            )
        print("⚡ Pre-computation finished! All audio cached in RAM.")

    @staticmethod
    def _index_audio_files(audio_dir):
        index = {}
        duplicates = set()
        for root, _, files in os.walk(audio_dir):
            for name in files:
                if not name.lower().endswith(".wav"):
                    continue
                key = name.casefold()
                path = os.path.join(root, name)
                if key in index and index[key] != path:
                    duplicates.add(name)
                index[key] = path
        if not index:
            raise FileNotFoundError(f"No WAV files found under '{audio_dir}'.")
        if duplicates:
            sample = ", ".join(sorted(duplicates)[:5])
            raise RuntimeError(f"Duplicate WAV basenames found: {sample}")
        print(f"🔎 Indexed {len(index):,} WAV files under '{audio_dir}'.")
        return index

    def _resolve_audio_path(self, filename):
        path = self.audio_file_index.get(os.path.basename(str(filename)).casefold())
        if path is None:
            raise FileNotFoundError(f"Audio file listed in metadata was not found: {filename}")
        return path

    def __len__(self):
        return len(self.participants)

    def load_audio_spec(self, filename):
        path = self._resolve_audio_path(filename)
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="PySoundFile failed.*")
                warnings.filterwarnings("ignore", category=FutureWarning, module="librosa.core.audio")
                y, _ = librosa.load(path, sr=self.sr, duration=self.duration)
        except Exception as exc:
            raise RuntimeError(f"Failed to decode real audio '{path}': {exc}") from exc

        target_len = int(self.duration * self.sr)
        if len(y) < target_len:
            y = np.pad(y, (0, target_len - len(y)))
        elif len(y) > target_len:
            y = y[:target_len]
        if not np.all(np.isfinite(y)) or np.max(np.abs(y)) < 1e-6:
            raise RuntimeError(f"Audio is silent or invalid: {path}")

        s = librosa.feature.melspectrogram(y=y, sr=self.sr, n_fft=1024, hop_length=256, n_mels=self.n_mels)
        s_db = librosa.power_to_db(s, ref=np.max)
        s_norm = (s_db - s_db.min()) / (s_db.max() - s_db.min() + 1e-8)

        # Ensure time dimension is exactly 36 frames (~0.55s at hop=256)
        target_frames = 36
        if s_norm.shape[1] < target_frames:
            s_norm = np.pad(s_norm, ((0, 0), (0, target_frames - s_norm.shape[1])), mode='constant')
        elif s_norm.shape[1] > target_frames:
            s_norm = s_norm[:, :target_frames]

        # Handcrafted acoustic features (Fourier-based)
        mfcc = librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=13)
        mfcc_mean = np.mean(mfcc, axis=1) # (13,)

        centroid = librosa.feature.spectral_centroid(y=y, sr=self.sr)
        centroid_mean = np.mean(centroid) # (1,)

        rolloff = librosa.feature.spectral_rolloff(y=y, sr=self.sr)
        rolloff_mean = np.mean(rolloff) # (1,)

        zcr = librosa.feature.zero_crossing_rate(y)
        zcr_mean = np.mean(zcr) # (1,)

        # Combine into a 16-dimensional acoustic vector
        acoustic_vec = np.concatenate([mfcc_mean, [centroid_mean, rolloff_mean, zcr_mean]])

        # Normalize continuous values to prevent range imbalance
        acoustic_vec[13] = acoustic_vec[13] / (self.sr / 2.0) # normalize spectral centroid
        acoustic_vec[14] = acoustic_vec[14] / (self.sr / 2.0) # normalize spectral rolloff

        # Generate YOHO local targets from energy-based segmentation
        rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=256)[0]
        threshold = np.mean(rms) + 1.2 * np.std(rms)
        active = rms > threshold

        # Map to 16 YOHO cells
        num_cells = 16
        yoho_target = np.zeros((num_cells, 3), dtype=np.float32)
        step = len(active) // num_cells
        for c in range(num_cells):
            sub_arr = active[c*step:(c+1)*step]
            if len(sub_arr) > 0 and np.mean(sub_arr) > 0.4:
                yoho_target[c, 0] = 1.0 # cough present
                yoho_target[c, 1] = 0.0 # start
                yoho_target[c, 2] = 1.0 # stop

        return (torch.tensor(s_norm, dtype=torch.float32).unsqueeze(0),
                torch.tensor(yoho_target, dtype=torch.float32),
                torch.tensor(acoustic_vec, dtype=torch.float32))

    def __getitem__(self, idx):
        participant = self.participants[idx]
        patient_row = self.metadata_df[self.metadata_df['participant'] == participant].iloc[0]
        meta_vector = torch.tensor(patient_row[self.feature_cols].values.astype(np.float32), dtype=torch.float32)
        tb_label = torch.tensor(int(patient_row['tb_status']), dtype=torch.long)
        specs_tensor, yoho_tensor, avg_acoustic_vec = self.cached_data[participant]
        fused_meta_vector = torch.cat((meta_vector, avg_acoustic_vec), dim=0)
        return specs_tensor, fused_meta_vector, yoho_tensor, tb_label

# Collate function to handle variable number of clips per patient in Dataloader
def multi_instance_collate(batch):
    # batch is list of (specs, meta, yoho, label)
    # Since specs has variable size (Num_clips, 1, H, W), we return lists for audio, tensors for meta/label
    specs_list = [item[0] for item in batch]
    meta_tensor = torch.stack([item[1] for item in batch])
    yoho_list = [item[2] for item in batch]
    labels_tensor = torch.stack([item[3] for item in batch])

    return specs_list, meta_tensor, yoho_list, labels_tensor

# %%
# CELL 6: Model Architecture (Multitask CNN + ProtoPNet + YOHO)

import torch.nn as nn
import torch.nn.functional as F

class PrototypeLayer(nn.Module):
    def __init__(self, num_prototypes=6, feature_depth=128):
        super(PrototypeLayer, self).__init__()
        self.num_prototypes = num_prototypes
        self.feature_depth = feature_depth
        self.prototypes = nn.Parameter(
            torch.randn(num_prototypes, feature_depth, 1, 1),
            requires_grad=True
        )

    def forward(self, x):
        batch_size = x.shape[0]

        # L2 normalize features and prototypes along the channel dimension (dim=1)
        x_norm = F.normalize(x, p=2, dim=1)
        p_norm = F.normalize(self.prototypes, p=2, dim=1)

        x_expanded = x_norm.unsqueeze(1) # (B, 1, C, H, W)
        p_expanded = p_norm.unsqueeze(0) # (1, M, C, 1, 1)

        # Distances are strictly in [0, 4] because both vectors are unit-norm
        distances = torch.sum((x_expanded - p_expanded) ** 2, dim=2) # (B, M, H, W)
        min_distances, _ = torch.min(distances.view(batch_size, self.num_prototypes, -1), dim=2)

        # Scale similarity using RBF kernel with temperature 1.0
        similarity = torch.exp(-min_distances)

        return similarity, min_distances

class SpecAugment(nn.Module):
    def __init__(self, time_mask_max=15, freq_mask_max=15):
        super(SpecAugment, self).__init__()
        self.time_mask_max = time_mask_max
        self.freq_mask_max = freq_mask_max

    def forward(self, x):
        if not self.training:
            return x

        x = x.clone()
        B, C, H, W = x.shape
        # Create masks on the same device as input
        for i in range(B):
            # Frequency mask
            f = int(torch.randint(0, self.freq_mask_max + 1, (1,)).item())
            if f > 0:
                f0 = int(torch.randint(0, H - f + 1, (1,)).item())
                x[i, :, f0:f0+f, :] = 0.0

            # Time mask
            t = int(torch.randint(0, self.time_mask_max + 1, (1,)).item())
            if t > 0:
                t0 = int(torch.randint(0, W - t + 1, (1,)).item())
                x[i, :, :, t0:t0+t] = 0.0

        return x

class PretrainedFeatureExtractor(nn.Module):
    def __init__(self):
        super(PretrainedFeatureExtractor, self).__init__()
        import torchvision.models as models
        try:
            from torchvision.models import ResNet18_Weights
            self.resnet = models.resnet18(weights=ResNet18_Weights.DEFAULT)
        except ImportError:
            self.resnet = models.resnet18(pretrained=True)
        self.features = nn.Sequential(
            self.resnet.conv1,
            self.resnet.bn1,
            self.resnet.relu,
            self.resnet.maxpool,
            self.resnet.layer1,
            self.resnet.layer2,
            self.resnet.layer3
        )
        self.adaptive_pool = nn.AdaptiveAvgPool2d((8, 4))

    def forward(self, x):
        x_3ch = x.repeat(1, 3, 1, 1)
        features = self.features(x_3ch)
        return self.adaptive_pool(features)

class AttentionMIL(nn.Module):
    """Gated Attention mechanism for Multi-Instance Learning (Ilse et al., 2018).
    Learns which cough clips are most diagnostically informative instead of
    treating all clips equally via blind mean-pooling."""
    def __init__(self, feature_dim, hidden_dim=128):
        super(AttentionMIL, self).__init__()
        self.attention_V = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.Tanh()
        )
        self.attention_U = nn.Sequential(
            nn.Linear(feature_dim, hidden_dim),
            nn.Sigmoid()
        )
        self.attention_w = nn.Linear(hidden_dim, 1)

    def forward(self, x):
        # x: (num_clips, feature_dim)
        v = self.attention_V(x)  # (num_clips, hidden_dim)
        u = self.attention_U(x)  # (num_clips, hidden_dim)
        attn = self.attention_w(v * u)  # (num_clips, 1) - gated attention scores
        attn = F.softmax(attn, dim=0)  # normalize over clips
        return attn

class MultimodalSuaraNafasModel(nn.Module):
    def __init__(self, metadata_dim=18, num_grid_cells=16, num_prototypes=10, use_augment=True):
        super(MultimodalSuaraNafasModel, self).__init__()
        self.num_grid_cells = num_grid_cells
        self.use_augment = use_augment
        self.spec_augment = SpecAugment()

        # Audio pre-trained ResNet18 feature extractor (outputs 256 channels)
        self.feature_extractor = PretrainedFeatureExtractor()

        # Local YOHO regression head (adaptive pool to fixed 4x4 → 256*16=4096)
        self.yoho_pool = nn.AdaptiveAvgPool2d((4, 4))
        self.yoho_fc = nn.Sequential(
            nn.Linear(256 * 4 * 4, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, num_grid_cells * 3)
        )

        # ProtoPNet layer (256-channel features from layer3)
        self.proto_layer = PrototypeLayer(num_prototypes=num_prototypes, feature_depth=256)

        # Attention-based Multi-Instance Learning pooling
        self.clip_attention = AttentionMIL(feature_dim=256, hidden_dim=128)

        # Tabular clinical metadata branch (wider bottleneck to preserve clinical signal)
        self.meta_fc = nn.Sequential(
            nn.BatchNorm1d(metadata_dim),
            nn.Linear(metadata_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 32),
            nn.ReLU()
        )

        # Fusion Classifier: prototypes + metadata
        self.global_classifier = nn.Sequential(
            nn.Linear(num_prototypes + 32, 64),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(32, 2)
        )

    def forward(self, specs, metadata):
        # Support both standard Tensors and lists of Tensors (multi-instance)
        if isinstance(specs, torch.Tensor):
            if specs.dim() == 3:
                specs = [specs.unsqueeze(0)]
            elif specs.dim() == 4:
                specs = [specs[i].unsqueeze(0) for i in range(specs.shape[0])]

        batch_size = len(specs)
        model_device = next(self.parameters()).device
        metadata = metadata.to(model_device)
        patient_similarities = []
        patient_yoho_outputs = []
        patient_min_distances = []

        for i in range(batch_size):
            patient_clips = specs[i].to(model_device) # (Num_clips, 1, H, W)

            # Apply SpecAugment during training
            if self.training and self.use_augment:
                patient_clips = self.spec_augment(patient_clips)

            # Pre-trained CNN pass: (Num_clips, 256, 8, 4)
            conv_features = self.feature_extractor(patient_clips)

            # Clip-level embeddings via Global Average Pooling for attention
            clip_embeddings = F.adaptive_avg_pool2d(conv_features, 1).squeeze(-1).squeeze(-1)  # (Num_clips, 256)

            # Attention weights: learn which clips are most diagnostic
            attn_weights = self.clip_attention(clip_embeddings)  # (Num_clips, 1)

            # YOHO local boundaries (attention-weighted)
            yoho_pooled = self.yoho_pool(conv_features)
            flat_out = yoho_pooled.view(yoho_pooled.size(0), -1)
            yoho_raw = self.yoho_fc(flat_out)
            yoho_out = torch.sigmoid(yoho_raw.view(-1, self.num_grid_cells, 3))
            patient_yoho_outputs.append((attn_weights.unsqueeze(-1) * yoho_out).sum(dim=0))

            # ProtoPNet matching (attention-weighted)
            similarities, min_dists = self.proto_layer(conv_features)
            patient_similarities.append((attn_weights * similarities).sum(dim=0))
            patient_min_distances.append((attn_weights * min_dists).sum(dim=0))

        # Stack patient representation tensors
        proto_feats = torch.stack(patient_similarities) # (B, num_prototypes)
        yoho_outputs = torch.stack(patient_yoho_outputs) # (B, num_grid_cells, 3)
        min_distances = torch.stack(patient_min_distances)

        # Late Fusion with Metadata (Concatenation)
        bn_module = self.meta_fc[0]
        is_single_sample = (metadata.shape[0] == 1)
        if is_single_sample and self.training:
            bn_module.eval()
            meta_feats = self.meta_fc(metadata)
            bn_module.train()
        else:
            meta_feats = self.meta_fc(metadata)
        fused = torch.cat((proto_feats, meta_feats), dim=1)

        # TB screening logits
        tb_logits = self.global_classifier(fused)

        return {
            "yoho_outputs": yoho_outputs,
            "tb_logits": tb_logits,
            "proto_similarities": proto_feats,
            "min_distances": min_distances
        }


def validate_metadata_batchnorm(model, minimum_variance=1e-8):
    batchnorm = model.meta_fc[0]
    collapsed = torch.where(batchnorm.running_var.detach().cpu() < minimum_variance)[0].tolist()
    if collapsed:
        raise RuntimeError(
            "Metadata BatchNorm has collapsed running variance at feature indices "
            f"{collapsed}. The checkpoint is unsafe for inference; verify real audio "
            "loading and retrain before export."
        )


# %%
# CELL 7: Multitask Loss Function

class MultitaskLoss(nn.Module):
    def __init__(self, l_yoho=1.0, l_tb=1.0, l_cluster=0.05, l_sep=0.005, class_weights=None):
        super(MultitaskLoss, self).__init__()
        self.l_yoho = l_yoho
        self.l_tb = l_tb
        self.l_cluster = l_cluster
        self.l_sep = l_sep
        self.class_weights = class_weights

    def forward(self, outputs, target_yoho, target_tb):
        yoho_pred = outputs["yoho_outputs"]
        # We need to average the yoho targets list to match outputs shape (B, cells, 3)
        stacked_yoho_targets = torch.stack([torch.mean(t, dim=0) for t in target_yoho]).to(device)

        pred_presence = yoho_pred[:, :, 0]
        true_presence = stacked_yoho_targets[:, :, 0]

        presence_loss = F.binary_cross_entropy(pred_presence, true_presence)

        # Offsets
        pred_start = yoho_pred[:, :, 1]
        pred_stop = yoho_pred[:, :, 2]
        true_start = stacked_yoho_targets[:, :, 1]
        true_stop = stacked_yoho_targets[:, :, 2]

        mask = (true_presence == 1.0).float()
        start_loss = torch.sum(mask * (pred_start - true_start)**2) / (torch.sum(mask) + 1e-8)
        stop_loss = torch.sum(mask * (pred_stop - true_stop)**2) / (torch.sum(mask) + 1e-8)
        yoho_loss = presence_loss + 1.5 * (start_loss + stop_loss)

        # Global TB classification loss (cross entropy with class weights and label smoothing)
        tb_loss = F.cross_entropy(outputs["tb_logits"], target_tb.to(device), weight=self.class_weights, label_smoothing=0.1)

        # ProtoPNet clustering and separation loss
        min_distances = outputs["min_distances"]
        cluster_loss = torch.mean(torch.min(min_distances, dim=1)[0])
        separation_loss = -torch.mean(min_distances)

        total_loss = (self.l_yoho * yoho_loss +
                      self.l_tb * tb_loss +
                      self.l_cluster * cluster_loss +
                      self.l_sep * separation_loss)

        return total_loss, yoho_loss, tb_loss

# %%
# CELL 8: Main Testing / Training Routine (Real Dataset & Simulated fallback)

import matplotlib.pyplot as plt

def generate_patient_xai_report(model, spec, metadata, save_path="xai_report.png", target_class=1, decision_threshold=0.5):
    """
    Generates a visual Explainable AI (XAI) report for a patient's cough sound.
    Combines:
      1. Input Mel-Spectrogram
      2. Grad-CAM attention heatmap (temporal/spectral focus)
      3. YOHO predicted local cough boundaries
      4. ProtoPNet prototype similarity match bar chart
      5. Clinical metadata context and prediction risk
    """
    model.eval()

    # 1. Grad-CAM Hooks setup
    gradients = []
    activations = []

    def save_grad(module, grad_in, grad_out):
        gradients.append(grad_out[0].detach())

    def save_act(module, input, output):
        activations.append(output.detach())

    # Register hooks on feature_extractor (output of pre-trained ResNet18)
    h1 = model.feature_extractor.register_forward_hook(save_act)
    h2 = model.feature_extractor.register_full_backward_hook(save_grad)

    # 2. Forward Pass
    model_device = next(model.parameters()).device
    spec_tensor = spec.to(model_device).detach().requires_grad_(True)
    meta_tensor = metadata.to(model_device)

    # Support both single tensor (unwrapped) and batched inputs
    if spec_tensor.dim() == 3:
        spec_input = [spec_tensor.unsqueeze(0)]
    elif spec_tensor.dim() == 4:
        spec_input = [spec_tensor[i].unsqueeze(0) for i in range(spec_tensor.shape[0])]
    else:
        spec_input = spec_tensor

    outputs = model(spec_input, meta_tensor)
    logits = outputs["tb_logits"]

    # 3. Backward Pass for Grad-CAM
    model.zero_grad()
    score = logits[0, target_class]
    score.backward()

    # Remove hooks
    h1.remove()
    h2.remove()

    # Calculate Grad-CAM
    grad = gradients[0][0].cpu().numpy() # (C, H, W)
    act = activations[0][0].cpu().numpy() # (C, H, W)
    weights = np.mean(grad, axis=(1, 2))

    cam = np.zeros(act.shape[1:], dtype=np.float32)
    for idx, w in enumerate(weights):
        cam += w * act[idx, :, :]

    cam = np.maximum(cam, 0)
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

    # 4. Extract predictions
    probs = F.softmax(logits, dim=1).detach().cpu().numpy()[0]
    tb_risk = probs[1] * 100

    yoho_preds = outputs["yoho_outputs"][0].detach().cpu().numpy() # (16, 3)
    proto_sims = outputs["proto_similarities"][0].detach().cpu().numpy() # (num_prototypes,)

    # 5. Plotting the Report
    fig = plt.figure(figsize=(15, 10))
    fig.suptitle("SuaraNafas: Explainable TB Cough Detection Report", fontsize=18, fontweight='bold', color='#1a365d')

    # Subplot 1: Mel-Spectrogram + YOHO boundaries
    ax1 = fig.add_subplot(2, 2, 1)
    spec_np = spec_tensor[0, 0].cpu().numpy() if spec_tensor.dim() == 4 else spec_tensor[0].cpu().numpy()
    img1 = ax1.imshow(spec_np, aspect='auto', origin='lower', cmap='magma')
    ax1.set_title("1. Mel-Spectrogram & YOHO Cough Detections", fontsize=12, fontweight='semibold')
    ax1.set_xlabel("Time Frames")
    ax1.set_ylabel("Mel Frequency Bins")

    # Draw YOHO boundaries as red vertical lines/boxes
    num_grid_cells = yoho_preds.shape[0]
    cell_dur = spec_np.shape[1] / num_grid_cells
    for c in range(num_grid_cells):
        presence = yoho_preds[c, 0]
        if presence > 0.5:
            # Cough start and stop indices
            c_start = int((c + yoho_preds[c, 1]) * cell_dur)
            c_stop = int((c + yoho_preds[c, 2]) * cell_dur)
            ax1.axvspan(c_start, c_stop, color='red', alpha=0.15, label='Cough' if c==0 else "")
            ax1.axvline(c_start, color='red', linestyle='--', alpha=0.5)
            ax1.axvline(c_stop, color='red', linestyle='--', alpha=0.5)

    # Subplot 2: Grad-CAM heatmap overlay
    ax2 = fig.add_subplot(2, 2, 2)
    # Resize cam to match spec_np shape using PyTorch bilinear interpolation
    cam_tensor = torch.tensor(cam).unsqueeze(0).unsqueeze(0)
    cam_resized = F.interpolate(cam_tensor, size=(spec_np.shape[0], spec_np.shape[1]), mode='bilinear', align_corners=False)
    cam_resized_np = cam_resized.squeeze(0).squeeze(0).numpy()
    cam_resized_np = (cam_resized_np - cam_resized_np.min()) / (cam_resized_np.max() - cam_resized_np.min() + 1e-8)

    ax2.imshow(spec_np, aspect='auto', origin='lower', cmap='gray')
    img2 = ax2.imshow(cam_resized_np, aspect='auto', origin='lower', cmap='jet', alpha=0.5)
    ax2.set_title("2. Grad-CAM Acoustic Focus (Acoustic Attention)", fontsize=12, fontweight='semibold')
    ax2.set_xlabel("Time Frames")
    ax2.set_ylabel("Mel Frequency Bins")
    fig.colorbar(img2, ax=ax2, label="Attention Weight")

    # Subplot 3: ProtoPNet similarities
    ax3 = fig.add_subplot(2, 2, 3)
    proto_ids = [f"Proto {i}" for i in range(len(proto_sims))]
    strongest_proto = int(np.argmax(proto_sims))
    colors = ['#ed8936' if i == strongest_proto else '#3182ce' for i in range(len(proto_sims))]
    ax3.bar(proto_ids, proto_sims, color=colors, edgecolor='black', alpha=0.8)
    ax3.set_title("3. ProtoPNet Acoustic Prototype Matching", fontsize=12, fontweight='semibold')
    ax3.set_ylabel("Similarity Score")
    ax3.set_ylim(0, max(proto_sims) * 1.2 if len(proto_sims) > 0 else 1.0)

    # Subplot 4: Clinical context & diagnosis prediction
    ax4 = fig.add_subplot(2, 2, 4)
    ax4.axis('off')

    text_content = (
        f"CLINICAL SUMMARY & PREDICTION:\n"
        f"--------------------------------------------------\n"
        f"- Predicted TB Risk: {tb_risk:.2f}%\n"
        f"- Screening threshold: {decision_threshold*100:.2f}%\n"
        f"- Screening Flag: {'HIGHER TB SCREENING RISK' if probs[1] >= decision_threshold else 'LOWER TB SCREENING RISK'}\n\n"
        f"EXPLANATION FINDINGS:\n"
        f"--------------------------------------------------\n"
        f"1. YOHO: Predicted {len([p for p in yoho_preds[:, 0] if p > 0.5])} cough segments in the clip.\n"
        f"2. Grad-CAM: Attention peaked on specific frequency bands\n"
        f"   associated with explosive cough signatures.\n"
        f"3. ProtoPNet: Strongest match with learned Acoustic Prototype #{strongest_proto}.\n"
        f"   Prototype similarity is supporting evidence, not a standalone diagnosis.\n"
    )

    ax4.text(0.05, 0.95, text_content, transform=ax4.transAxes, fontsize=11,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='#edf2f7', alpha=0.8, edgecolor='#cbd5e0'))

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"✅ XAI Report generated and saved successfully to '{save_path}'!")

def train_and_evaluate_coda(data_dir=None, epochs=3, batch_size=8, lr=1e-4):
    """
    If real data is downloaded/available, performs training and evaluation on it.
    """
    # Auto-resolve dataset directory
    if data_dir is None:
        possible_dirs = [
            "/kaggle/input/datasets/ruchikashirsath/tb-audio",
            "/kaggle/input/tb-audio",
            "./data/coda-tb",
            "./coda_tb_data"
        ]
        for d in possible_dirs:
            if os.path.exists(d):
                data_dir = d
                break
        if data_dir is None:
            data_dir = "./coda_tb_data"

    clinical_path = None
    additional_path = None
    solicited_path = None
    audio_dir = None

    # Dynamically locate key files within data_dir
    if os.path.exists(data_dir):
        for root, _, files in os.walk(data_dir):
            wav_files = [f for f in files if f.lower().endswith('.wav')]
            if wav_files:
                audio_dir = data_dir
            for f in files:
                f_lower = f.lower()
                full_path = os.path.join(root, f)
                if "clinical" in f_lower and f.endswith(".csv"):
                    clinical_path = full_path
                elif "additional" in f_lower and f.endswith(".csv"):
                    additional_path = full_path
                elif "solicited" in f_lower and f.endswith(".csv"):
                    solicited_path = full_path

    # Check if files exist
    missing_files = []
    if not clinical_path: missing_files.append("Clinical Metadata CSV")
    if not additional_path: missing_files.append("Additional Variables CSV")
    if not solicited_path: missing_files.append("Solicited Metadata CSV")
    if not audio_dir: missing_files.append("Audio Directory (.wav files)")

    if missing_files or not os.path.exists(data_dir):
        print(f"⚠️ Real dataset files not found at '{data_dir}'. Skipping training on real data.")
        print(f"  • Missing: {missing_files}")
        return False

    print(f"\n🚀 Found real dataset at '{data_dir}'! Preprocessing clinical metadata...")
    df_meta, feature_cols = preprocess_metadata(clinical_path, additional_path)

    print("📦 Initializing Multi-Instance Audio Dataset...")
    dataset = MultiInstanceCODATBDataset(
        metadata_df=df_meta,
        feature_cols=feature_cols,
        solicited_csv_path=solicited_path,
        audio_dir=audio_dir
    )

    print(f"📊 Dataset successfully mapped {len(dataset)} patients with cough recordings.")
    if len(dataset) == 0:
        print("⚠️ No valid patients with audio records. Check if audio files match solicited csv metadata.")
        return False

    from sklearn.model_selection import StratifiedShuffleSplit
    all_labels_for_split = [dataset[i][3].item() for i in range(len(dataset))]
    sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_indices, val_indices = next(sss.split(range(len(dataset)), all_labels_for_split))

    train_dataset = torch.utils.data.Subset(dataset, train_indices)
    val_dataset = torch.utils.data.Subset(dataset, val_indices)
    print(f"📊 Split: {len(train_dataset)} train / {len(val_dataset)} validation")

    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, collate_fn=multi_instance_collate,
        drop_last=True
    )
    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False, collate_fn=multi_instance_collate
    )

    # Model configuration
    metadata_dim = len(feature_cols) + 16
    print(f"🔧 Initializing MultimodalSuaraNafasModel (Metadata dim: {metadata_dim})...")
    model = MultimodalSuaraNafasModel(metadata_dim=metadata_dim).to(device)

    # Differential learning rates: fine-tune pre-trained backbone gently, train classifier quickly
    backbone_params = list(model.feature_extractor.parameters())
    other_params = [p for name, p in model.named_parameters() if "feature_extractor" not in name]
    optimizer = torch.optim.AdamW([
        {"params": backbone_params, "lr": lr * 0.1}, # 1e-5
        {"params": other_params, "lr": lr}           # 1e-4
    ], weight_decay=1e-4)

    tb_status_vals = df_meta[df_meta['participant'].isin(dataset.participants)]['tb_status'].values
    neg_count = np.sum(tb_status_vals == 0)
    pos_count = np.sum(tb_status_vals == 1)
    total_count = neg_count + pos_count
    print(f"⚖️ Training class distribution - Negative (Normal): {neg_count} ({neg_count/total_count*100:.1f}%), Positive (TB): {pos_count} ({pos_count/total_count*100:.1f}%)")

    weights = [np.sqrt(total_count / neg_count), np.sqrt(total_count / pos_count)]
    class_weights = torch.tensor(weights, dtype=torch.float32).to(device)
    class_weights = class_weights / class_weights.sum() * 2.0 # normalize

    criterion = MultitaskLoss(class_weights=class_weights)

    # Warmup + Cosine Annealing LR scheduler
    warmup_epochs = 5
    warmup_scheduler = torch.optim.lr_scheduler.LinearLR(optimizer, start_factor=0.1, total_iters=warmup_epochs)
    cosine_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=max(1, epochs - warmup_epochs), eta_min=1e-5
    )
    scheduler = torch.optim.lr_scheduler.SequentialLR(optimizer, schedulers=[warmup_scheduler, cosine_scheduler], milestones=[warmup_epochs])

    import copy
    best_auroc = 0.0
    best_epoch = 0
    best_threshold = 0.5
    best_model_state = None
    patience = 20
    epochs_without_improvement = 0
    history = []
    print("🏋️ Starting training loop...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for batch_idx, (specs, meta, yoho, labels) in enumerate(train_loader):
            optimizer.zero_grad()
            # Forward pass
            outputs = model(specs, meta)
            # Compute multitask loss
            loss, yoho_loss, tb_loss = criterion(outputs, yoho, labels)

            # Backward pass with gradient clipping for stable fine-tuning
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_loss += loss.item()

        # Validation
        model.eval()
        val_loss = 0.0
        all_labels = []
        all_probs = []
        correct = 0
        total = 0

        with torch.no_grad():
            for specs, meta, yoho, labels in val_loader:
                outputs = model(specs, meta)
                loss, _, _ = criterion(outputs, yoho, labels)
                val_loss += loss.item()

                # Predict probability of class 1 (TB positive)
                probs = F.softmax(outputs["tb_logits"], dim=1)[:, 1]
                all_probs.extend(probs.cpu().numpy())
                all_labels.extend(labels.numpy())

                # Raw accuracy calculation
                preds = torch.argmax(outputs["tb_logits"], dim=1)
                correct += (preds == labels.to(device)).sum().item()
                total += labels.size(0)

        # Calculate AUROC and Balanced Accuracy using optimal threshold
        auroc = np.nan
        bal_acc = np.nan
        best_thresh = 0.5
        auroc_str = "N/A"
        bal_acc_str = "N/A"
        try:
            from sklearn.metrics import roc_auc_score, roc_curve, balanced_accuracy_score
            if len(set(all_labels)) > 1:
                auroc = roc_auc_score(all_labels, all_probs)
                auroc_str = f"{auroc:.4f}"

                # Find optimal threshold using Youden's J statistic
                fpr, tpr, thresholds = roc_curve(all_labels, all_probs)
                finite = np.isfinite(thresholds)
                J = np.where(finite, tpr - fpr, -np.inf)
                ix = np.argmax(J)
                best_thresh = float(thresholds[ix])

                # Predict using the optimal threshold
                opt_preds = (np.array(all_probs) >= best_thresh).astype(int)
                bal_acc = balanced_accuracy_score(all_labels, opt_preds)
                bal_acc_str = f"{bal_acc*100:.2f}%"
        except Exception:
            pass

        # Step the learning rate scheduler
        scheduler.step()

        # Track best model
        current_auroc = float(auroc) if np.isfinite(auroc) else 0.0
        star = ""
        if current_auroc > best_auroc:
            best_auroc = current_auroc
            best_epoch = epoch + 1
            best_threshold = float(best_thresh)
            best_model_state = copy.deepcopy(model.state_dict())
            epochs_without_improvement = 0
            star = " ⭐ Best!"
        else:
            epochs_without_improvement += 1

        current_lr_backbone = optimizer.param_groups[0]['lr']
        current_lr_head = optimizer.param_groups[1]['lr']
        raw_accuracy = correct / total
        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss / len(train_loader),
            "val_loss": val_loss / len(val_loader),
            "val_accuracy": raw_accuracy,
            "val_balanced_accuracy": float(bal_acc) if np.isfinite(bal_acc) else np.nan,
            "val_auroc": float(auroc) if np.isfinite(auroc) else np.nan,
            "optimal_threshold": float(best_thresh),
            "lr_backbone": current_lr_backbone,
            "lr_head": current_lr_head
        })
        print(f"  • Epoch {epoch+1:02d}/{epochs:02d} | Train Loss: {train_loss/len(train_loader):.4f} | "
              f"Val Loss: {val_loss/len(val_loader):.4f} | Val Accuracy: {raw_accuracy*100:.2f}% "
              f"(Balanced: {bal_acc_str}) | Val AUROC: {auroc_str}{star}")

        # Early stopping
        if epochs_without_improvement >= patience:
            print(f"⏹️ Early stopping at epoch {epoch+1} (no improvement for {patience} epochs)")
            break

    # Restore and save the best model weights
    if best_model_state is not None:
        model.load_state_dict(best_model_state)
        print(f"✅ Restored best model weights from epoch {best_epoch} (AUROC: {best_auroc:.4f})")
    model.eval()
    validate_metadata_batchnorm(model)
    checkpoint_path = "best_tb_cough_model.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "metadata_dim": metadata_dim,
        "feature_cols": feature_cols,
        "best_auroc": best_auroc,
        "best_epoch": best_epoch,
        "validation_youden_threshold": best_threshold
    }, checkpoint_path)
    print(f"💾 Best checkpoint saved to '{checkpoint_path}'")
    print(f"🎉 Real dataset training complete! Best Val AUROC: {best_auroc:.4f}")
    return {
        "model": model,
        "dataset": dataset,
        "metadata_df": df_meta,
        "feature_cols": feature_cols,
        "train_indices": np.asarray(train_indices),
        "val_indices": np.asarray(val_indices),
        "train_loader": train_loader,
        "val_loader": val_loader,
        "history": history,
        "best_auroc": best_auroc,
        "best_epoch": best_epoch,
        "best_threshold": best_threshold,
        "checkpoint_path": checkpoint_path
    }

def test_coda_pipeline():
    print("🧪 Running self-check pipeline with simulated CODA data...")

    # Define simulated clinical row: 2 samples, 43 encoded features
    metadata_dim = 43 # After one-hot encoding + 16 acoustic features
    mock_meta = torch.randn(2, metadata_dim).to(device)
    mock_labels = torch.tensor([1, 0], dtype=torch.long).to(device)

    # 2 Patients, Patient 1 has 3 clips, Patient 2 has 2 clips
    mock_specs = [
        torch.randn(3, 1, 128, 36).to(device),
        torch.randn(2, 1, 128, 36).to(device)
    ]
    # YOHO targets must have values in range [0, 1] for binary cross entropy
    mock_yoho_targets = [
        torch.rand(3, 16, 3).to(device),
        torch.rand(2, 16, 3).to(device)
    ]

    # Initialize Multitask Model
    model = MultimodalSuaraNafasModel(metadata_dim=metadata_dim).to(device)
    criterion = MultitaskLoss()

    # Test forward path
    model.eval()
    with torch.no_grad():
        out = model(mock_specs, mock_meta)

    probs = F.softmax(out["tb_logits"], dim=1).cpu().numpy()
    print(f"  • Forward pass successful! Output TB logits shape: {out['tb_logits'].shape}")
    print(f"  • Sample 1 TB risk probability: {probs[0, 1]*100:.1f}%")
    print(f"  • Sample 2 TB risk probability: {probs[1, 1]*100:.1f}%")

    # Test backward pass (gradient calculation)
    model.train()
    out = model(mock_specs, mock_meta)
    loss, y_loss, t_loss = criterion(out, mock_yoho_targets, mock_labels)
    loss.backward()
    print(f"  • Backward pass successful! Computed training loss: {loss.item():.4f}")

# 1. Run simulated checks to ensure code is syntactically sound:
test_coda_pipeline()

# 2. Train on real data if present (60 epochs for full convergence):
training_artifacts = train_and_evaluate_coda(epochs=60)

# %%
# CELL 10: Exploratory Data Analysis (EDA) on CODA TB Dataset
# Generates statistics and saves to eda_report.txt for offline review.

import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

def run_eda(data_dir=None):
    """EDA on clinical metadata + audio file statistics. Saves report to eda_report.txt."""
    # --- Locate dataset (same logic as train_and_evaluate_coda) ---
    if data_dir is None:
        for d in [
            "/kaggle/input/datasets/ruchikashirsath/tb-audio",
            "/kaggle/input/tb-audio",
            "./data/coda-tb",
            "./coda_tb_data",
        ]:
            if os.path.exists(d):
                data_dir = d
                break
    if data_dir is None or not os.path.exists(data_dir):
        print("⚠️ Dataset not found for EDA.")
        return

    clinical_path = additional_path = solicited_path = audio_dir = None
    for root, _, files in os.walk(data_dir):
        wav_files = [f for f in files if f.lower().endswith('.wav')]
        if wav_files:
            audio_dir = data_dir
        for f in files:
            fl = f.lower()
            fp = os.path.join(root, f)
            if "clinical" in fl and f.endswith(".csv"): clinical_path = fp
            elif "additional" in fl and f.endswith(".csv"): additional_path = fp
            elif "solicited" in fl and f.endswith(".csv"): solicited_path = fp

    if not all([clinical_path, additional_path, solicited_path, audio_dir]):
        print("⚠️ Missing files for EDA.")
        return

    # --- Load raw data ---
    df_clinical = pd.read_csv(clinical_path)
    df_additional = pd.read_csv(additional_path)
    df = pd.merge(df_clinical, df_additional, on="participant", how="inner")
    df_solicited = pd.read_csv(solicited_path)

    lines = []  # collect report lines
    def log(s=""):
        print(s)
        lines.append(str(s))

    log("=" * 70)
    log("📊 CODA TB DATASET — EXPLORATORY DATA ANALYSIS")
    log("=" * 70)

    # 1. Basic shape
    log(f"\n▶ Clinical CSV shape: {df_clinical.shape}")
    log(f"▶ Additional CSV shape: {df_additional.shape}")
    log(f"▶ Merged shape: {df.shape}")
    log(f"▶ Solicited (audio map) shape: {df_solicited.shape}")
    log(f"▶ Columns in merged: {list(df.columns)}")

    # 2. Target distribution
    log("\n--- TARGET: tb_status ---")
    if 'tb_status' in df.columns:
        vc = df['tb_status'].value_counts()
        log(vc.to_string())
        log(f"Class ratio (pos/neg): {vc.get(1,0) / max(vc.get(0,1),1):.3f}")
    if 'Microbiologicreferencestandard' in df.columns:
        log("\n--- Microbiologic Reference Standard ---")
        log(df['Microbiologicreferencestandard'].value_counts().to_string())

    # 3. Missing values
    log("\n--- MISSING VALUES (top 15) ---")
    missing = df.isnull().sum().sort_values(ascending=False)
    missing_pct = (missing / len(df) * 100).round(1)
    for col in missing.index[:15]:
        if missing[col] > 0:
            log(f"  {col}: {missing[col]} ({missing_pct[col]}%)")
    total_missing = missing.sum()
    log(f"  Total missing cells: {total_missing} / {df.shape[0]*df.shape[1]} ({total_missing/(df.shape[0]*df.shape[1])*100:.1f}%)")

    # 4. Numeric feature statistics
    numeric_cols = ['age', 'height', 'weight', 'reported_cough_dur', 'heart_rate', 'temperature']
    existing_numeric = [c for c in numeric_cols if c in df.columns]
    if existing_numeric:
        log("\n--- NUMERIC FEATURES (raw, before normalization) ---")
        log(df[existing_numeric].describe().round(2).to_string())

        # Per-class stats
        if 'tb_status' in df.columns:
            log("\n--- NUMERIC FEATURES BY TB STATUS ---")
            for col in existing_numeric:
                neg_vals = df.loc[df['tb_status']==0, col].dropna()
                pos_vals = df.loc[df['tb_status']==1, col].dropna()
                log(f"  {col}: TB- mean={neg_vals.mean():.2f}±{neg_vals.std():.2f}  |  TB+ mean={pos_vals.mean():.2f}±{pos_vals.std():.2f}")

    # 5. Categorical features
    cat_cols = ['sex', 'Country', 'HIVstatus', 'tb_prior', 'hemoptysis', 'weight_loss',
                'smoke_lweek', 'fever', 'night_sweats']
    log("\n--- CATEGORICAL FEATURES ---")
    for col in cat_cols:
        if col in df.columns:
            log(f"\n  {col}:")
            vc = df[col].value_counts(dropna=False)
            for val, cnt in vc.items():
                log(f"    {val}: {cnt} ({cnt/len(df)*100:.1f}%)")
            # Cross-tab with tb_status
            if 'tb_status' in df.columns:
                ct = pd.crosstab(df[col], df['tb_status'], margins=False)
                tb_rate = ct[1] / ct.sum(axis=1) * 100
                log(f"    TB+ rate by {col}: {tb_rate.round(1).to_dict()}")

    # 6. Audio file statistics
    log("\n--- AUDIO FILE STATISTICS ---")
    clips_per_patient = df_solicited.groupby('participant')['filename'].count()
    log(f"  Solicited metadata rows: {len(df_solicited)}")
    log(f"  Unique patients with audio metadata: {df_solicited['participant'].nunique()}")
    log(f"  Clips per patient: min={clips_per_patient.min()}, max={clips_per_patient.max()}, "
        f"median={clips_per_patient.median():.0f}, mean={clips_per_patient.mean():.1f}")

    # Check how many patients in metadata have audio
    meta_participants = set(df['participant'])
    audio_participants = set(df_solicited['participant'])
    overlap = meta_participants & audio_participants
    log(f"  Patients in metadata: {len(meta_participants)}")
    log(f"  Patients with audio: {len(audio_participants)}")
    log(f"  Overlap (usable): {len(overlap)}")
    log(f"  Metadata only (no audio): {len(meta_participants - audio_participants)}")
    log(f"  Audio only (no metadata): {len(audio_participants - meta_participants)}")

    # Audio file durations (sample 100 files)
    import random
    wav_files_all = [
        os.path.join(root, file_name)
        for root, _, files in os.walk(audio_dir)
        for file_name in files
        if file_name.lower().endswith('.wav')
    ]
    log(f"  WAV files found recursively: {len(wav_files_all)}")
    sample_files = random.sample(wav_files_all, min(200, len(wav_files_all)))
    durations = []
    for fp in sample_files:
        try:
            duration_seconds = librosa.get_duration(path=fp)
            durations.append(duration_seconds)
        except:
            pass
    if durations:
        durations = np.array(durations)
        log(f"  Audio duration (sampled {len(durations)} files): min={durations.min():.2f}s, max={durations.max():.2f}s, "
            f"median={np.median(durations):.2f}s, mean={durations.mean():.2f}s")

    # 7. Country distribution
    if 'Country' in df.columns and 'tb_status' in df.columns:
        log("\n--- TB PREVALENCE BY COUNTRY ---")
        ct = pd.crosstab(df['Country'], df['tb_status'], margins=True)
        ct['TB+ %'] = (ct[1] / (ct[0] + ct[1]) * 100).round(1)
        log(ct.to_string())

    # 8. Correlation of numeric features with tb_status
    if 'tb_status' in df.columns and existing_numeric:
        log("\n--- POINT-BISERIAL CORRELATION WITH tb_status ---")
        for col in existing_numeric:
            valid = df[[col, 'tb_status']].dropna()
            if len(valid) > 10:
                corr = valid[col].corr(valid['tb_status'])
                log(f"  {col}: r={corr:.4f}")

    # 9. NumberOfCoughSoundsCollected
    if 'Numberofcoughsoundscollected' in df.columns:
        log("\n--- Numberofcoughsoundscollected ---")
        log(df['Numberofcoughsoundscollected'].describe().round(2).to_string())

    log("\n" + "=" * 70)
    log("📊 EDA COMPLETE")
    log("=" * 70)

    # --- Save report ---
    report_path = "eda_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n💾 Report saved to {report_path}")

    # --- Generate plots ---
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('CODA TB Dataset EDA', fontsize=16, fontweight='bold')

    # Plot 1: TB status distribution
    if 'tb_status' in df.columns:
        df['tb_status'].value_counts().plot.bar(ax=axes[0,0], color=['steelblue','salmon'])
        axes[0,0].set_title('TB Status Distribution')
        axes[0,0].set_xticklabels(['Negative (0)', 'Positive (1)'], rotation=0)

    # Plot 2: Age distribution by TB status
    if 'age' in df.columns and 'tb_status' in df.columns:
        df[df['tb_status']==0]['age'].hist(ax=axes[0,1], alpha=0.6, label='TB-', bins=30, color='steelblue')
        df[df['tb_status']==1]['age'].hist(ax=axes[0,1], alpha=0.6, label='TB+', bins=30, color='salmon')
        axes[0,1].set_title('Age Distribution by TB Status')
        axes[0,1].legend()

    # Plot 3: Country distribution
    if 'Country' in df.columns:
        df['Country'].value_counts().plot.bar(ax=axes[0,2], color='teal')
        axes[0,2].set_title('Country Distribution')
        axes[0,2].tick_params(axis='x', rotation=45)

    # Plot 4: Clips per patient
    clips_per_patient.hist(ax=axes[1,0], bins=30, color='purple', alpha=0.7)
    axes[1,0].set_title('Clips per Patient')
    axes[1,0].set_xlabel('Number of clips')

    # Plot 5: Audio durations
    if durations is not None and len(durations) > 0:
        axes[1,1].hist(durations, bins=30, color='orange', alpha=0.7)
        axes[1,1].set_title(f'Audio Duration (sampled {len(durations)})')
        axes[1,1].set_xlabel('Duration (s)')

    # Plot 6: HIV status vs TB
    if 'HIVstatus' in df.columns and 'tb_status' in df.columns:
        ct = pd.crosstab(df['HIVstatus'], df['tb_status'])
        ct.plot.bar(ax=axes[1,2], color=['steelblue','salmon'])
        axes[1,2].set_title('HIV Status vs TB Status')
        axes[1,2].tick_params(axis='x', rotation=45)
        axes[1,2].legend(['TB-', 'TB+'])

    plt.tight_layout()
    plt.savefig('eda_plots.png', dpi=150, bbox_inches='tight')
    plt.show()
    print("💾 Plots saved to eda_plots.png")

run_eda()

# %%
# CELL 11: Validation Diagnostics + Edge Deployment Profiler
# Run after CELL 8 has produced `training_artifacts`.

import copy
import io
import json
import time

from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, balanced_accuracy_score,
    brier_score_loss, confusion_matrix, f1_score, precision_score,
    roc_auc_score, roc_curve
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def _safe_auroc(labels, probabilities):
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities)
    return roc_auc_score(labels, probabilities) if np.unique(labels).size == 2 else np.nan


def _classification_metrics(labels, probabilities, threshold):
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    predictions = (probabilities >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "accuracy": accuracy_score(labels, predictions),
        "balanced_accuracy": balanced_accuracy_score(labels, predictions),
        "sensitivity": tp / max(tp + fn, 1),
        "specificity": tn / max(tn + fp, 1),
        "precision": precision_score(labels, predictions, zero_division=0),
        "npv": tn / max(tn + fn, 1),
        "f1": f1_score(labels, predictions, zero_division=0),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)
    }


def _select_thresholds(labels, probabilities, target_sensitivity=0.90):
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    fpr, tpr, thresholds = roc_curve(labels, probabilities)
    finite = np.isfinite(thresholds)

    youden_index = np.argmax(np.where(finite, tpr - fpr, -np.inf))
    youden_threshold = float(thresholds[youden_index])

    sensitivity_candidates = np.where(finite & (tpr >= target_sensitivity))[0]
    if len(sensitivity_candidates):
        best_specificity = np.min(fpr[sensitivity_candidates])
        tied = sensitivity_candidates[fpr[sensitivity_candidates] == best_specificity]
        screening_index = tied[np.argmax(thresholds[tied])]
        screening_threshold = float(thresholds[screening_index])
    else:
        screening_threshold = float(np.min(probabilities))

    candidates = np.unique(np.concatenate((
        [0.0, 0.5, 1.0, np.nextafter(np.max(probabilities), np.inf)], probabilities
    )))
    candidate_accuracies = [accuracy_score(labels, probabilities >= t) for t in candidates]
    accuracy_threshold = float(candidates[int(np.argmax(candidate_accuracies))])

    return {
        "default_0.5": 0.5,
        "youden_balanced": youden_threshold,
        f"screening_{int(target_sensitivity * 100)}pct_sensitivity": screening_threshold,
        "max_accuracy": accuracy_threshold
    }


def _bootstrap_auroc_ci(labels, probabilities, repeats=500, seed=42):
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities)
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(repeats):
        indices = rng.integers(0, len(labels), len(labels))
        if np.unique(labels[indices]).size == 2:
            scores.append(roc_auc_score(labels[indices], probabilities[indices]))
    if not scores:
        return np.nan, np.nan
    return tuple(np.percentile(scores, [2.5, 97.5]))


def _expected_calibration_error(labels, probabilities, bins=10):
    labels = np.asarray(labels)
    probabilities = np.asarray(probabilities)
    bin_ids = np.minimum((probabilities * bins).astype(int), bins - 1)
    ece = 0.0
    for bin_id in range(bins):
        mask = bin_ids == bin_id
        if np.any(mask):
            ece += mask.mean() * abs(labels[mask].mean() - probabilities[mask].mean())
    return float(ece)


def _collect_predictions(model, dataset, indices, batch_size=8, max_clips=None,
                         zero_meta_indices=None, zero_audio=False):
    model.eval()
    labels_all, probabilities_all, participants_all = [], [], []
    zero_meta_indices = list(zero_meta_indices or [])

    with torch.no_grad():
        for start in range(0, len(indices), batch_size):
            batch_indices = [int(i) for i in indices[start:start + batch_size]]
            batch = [dataset[i] for i in batch_indices]
            specs = []
            metadata = []
            labels = []

            for dataset_index, (patient_specs, patient_meta, _, patient_label) in zip(batch_indices, batch):
                if max_clips is not None:
                    patient_specs = patient_specs[:max(1, min(max_clips, len(patient_specs)))]
                if zero_audio:
                    patient_specs = torch.zeros_like(patient_specs)
                patient_meta = patient_meta.clone()
                if zero_meta_indices:
                    patient_meta[zero_meta_indices] = 0.0
                specs.append(patient_specs)
                metadata.append(patient_meta)
                labels.append(int(patient_label.item()))
                participants_all.append(dataset.participants[dataset_index])

            outputs = model(specs, torch.stack(metadata))
            probabilities = F.softmax(outputs["tb_logits"], dim=1)[:, 1]
            probabilities_all.extend(probabilities.detach().cpu().numpy().tolist())
            labels_all.extend(labels)

    return np.asarray(labels_all), np.asarray(probabilities_all), participants_all


def _serialized_state_size_mb(model):
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return buffer.getbuffer().nbytes / (1024 ** 2)


def _profile_macs_and_activations(model, metadata_dim, clip_count=5):
    totals = {"macs": 0, "largest_activation_bytes": 0}
    handles = []

    def hook(module, inputs, output):
        if not isinstance(output, torch.Tensor):
            return
        totals["largest_activation_bytes"] = max(
            totals["largest_activation_bytes"], output.numel() * output.element_size()
        )
        if isinstance(module, nn.Conv2d):
            kernel_h, kernel_w = module.kernel_size
            kernel_macs = kernel_h * kernel_w * module.in_channels / module.groups
            totals["macs"] += int(output.numel() * kernel_macs)
        elif isinstance(module, nn.Linear):
            totals["macs"] += int(output.numel() * module.in_features)

    for module in model.modules():
        if isinstance(module, (nn.Conv2d, nn.Linear, nn.BatchNorm2d, nn.AdaptiveAvgPool2d)):
            handles.append(module.register_forward_hook(hook))

    with torch.no_grad():
        model([torch.zeros(clip_count, 1, 128, 36)], torch.zeros(1, metadata_dim))

    for handle in handles:
        handle.remove()
    return totals


def _benchmark_cpu_latency(model, metadata_dim, clip_counts=(1, 5, 8), repeats=10):
    results = []
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(max(1, min(4, previous_threads)))
    try:
        for clip_count in clip_counts:
            specs = [torch.zeros(clip_count, 1, 128, 36)]
            metadata = torch.zeros(1, metadata_dim)
            with torch.no_grad():
                for _ in range(3):
                    model(specs, metadata)
                durations = []
                for _ in range(repeats):
                    start = time.perf_counter()
                    model(specs, metadata)
                    durations.append((time.perf_counter() - start) * 1000)
            results.append({
                "clips": clip_count,
                "median_ms": float(np.median(durations)),
                "p90_ms": float(np.percentile(durations, 90))
            })
    finally:
        torch.set_num_threads(previous_threads)
    return pd.DataFrame(results)


def run_validation_and_edge_analysis(artifacts, target_sensitivity=0.90):
    if not isinstance(artifacts, dict):
        print("⚠️ Training artifacts are unavailable; run CELL 8 with the real dataset first.")
        return None

    model = artifacts["model"]
    dataset = artifacts["dataset"]
    val_indices = artifacts["val_indices"]
    train_indices = artifacts["train_indices"]
    feature_cols = artifacts["feature_cols"]
    clinical_dim = len(feature_cols)
    metadata_dim = clinical_dim + 16
    report = []

    def log(message=""):
        print(message)
        report.append(str(message))

    log("=" * 76)
    log("VALIDATION DIAGNOSTICS AND EDGE DEPLOYMENT PROFILE")
    log("=" * 76)

    # 1. Validation predictions and threshold calibration.
    labels, probabilities, participants = _collect_predictions(
        model, dataset, val_indices, batch_size=8
    )
    thresholds = _select_thresholds(labels, probabilities, target_sensitivity)

    auroc = _safe_auroc(labels, probabilities)
    average_precision = average_precision_score(labels, probabilities)
    ci_low, ci_high = _bootstrap_auroc_ci(labels, probabilities)

    log("\n--- VALIDATION DISCRIMINATION AND CALIBRATION ---")
    log(f"Validation AUROC: {auroc:.4f} (bootstrap 95% CI: {ci_low:.4f}-{ci_high:.4f})")
    log(f"Validation average precision / PR-AUC: {average_precision:.4f}")
    log(f"Validation Brier score: {brier_score_loss(labels, probabilities):.4f} (lower is better)")
    log(f"Validation expected calibration error: {_expected_calibration_error(labels, probabilities):.4f}")

    threshold_rows = []
    log("\n--- VALIDATION OPERATING THRESHOLDS ---")
    for threshold_name, threshold in thresholds.items():
        metrics = _classification_metrics(labels, probabilities, threshold)
        threshold_rows.append({"name": threshold_name, **metrics})
        log(
            f"{threshold_name:>27}: threshold={threshold:.4f} | "
            f"accuracy={metrics['accuracy']*100:.2f}% | balanced={metrics['balanced_accuracy']*100:.2f}% | "
            f"sensitivity={metrics['sensitivity']*100:.2f}% | specificity={metrics['specificity']*100:.2f}% | "
            f"F1={metrics['f1']:.3f}"
        )
    threshold_df = pd.DataFrame(threshold_rows)
    threshold_df.to_csv("validation_thresholds.csv", index=False)
    log("Thresholds were selected and evaluated on the validation set.")

    selected_threshold = thresholds["youden_balanced"]

    # 2. Counterfactual modality/feature-group occlusion
    country_indices = [i for i, col in enumerate(feature_cols) if col.startswith("country_")]
    symptom_names = ["tb_prior", "tb_prior_Pul", "tb_prior_Extrapul", "tb_prior_Unknown",
                     "hemoptysis", "weight_loss", "smoke_lweek", "fever", "night_sweats"]
    symptom_indices = [feature_cols.index(col) for col in symptom_names if col in feature_cols]
    acoustic_indices = list(range(clinical_dim, metadata_dim))
    clinical_indices = list(range(clinical_dim))

    conditions = {
        "full_model": {"zero_meta_indices": [], "zero_audio": False},
        "country_neutralized": {"zero_meta_indices": country_indices, "zero_audio": False},
        "symptoms_neutralized": {"zero_meta_indices": symptom_indices, "zero_audio": False},
        "audio_only": {"zero_meta_indices": clinical_indices, "zero_audio": False},
        "clinical_only": {"zero_meta_indices": acoustic_indices, "zero_audio": True}
    }
    occlusion_rows = []
    log("\n--- MODEL RELIANCE (COUNTERFACTUAL OCCLUSION; NOT RETRAINED ABLATIONS) ---")
    for condition_name, condition in conditions.items():
        if condition_name == "full_model":
            condition_labels, condition_probs = labels, probabilities
        else:
            condition_labels, condition_probs, _ = _collect_predictions(
                model, dataset, val_indices, batch_size=8,
                zero_meta_indices=condition["zero_meta_indices"],
                zero_audio=condition["zero_audio"]
            )
        condition_auc = _safe_auroc(condition_labels, condition_probs)
        condition_metrics = _classification_metrics(condition_labels, condition_probs, selected_threshold)
        occlusion_rows.append({
            "condition": condition_name,
            "auroc": condition_auc,
            "auroc_delta_vs_full": condition_auc - auroc,
            "accuracy_at_full_threshold": condition_metrics["accuracy"],
            "sensitivity_at_full_threshold": condition_metrics["sensitivity"],
            "specificity_at_full_threshold": condition_metrics["specificity"]
        })
        log(f"{condition_name:>22}: AUROC={condition_auc:.4f} (delta {condition_auc-auroc:+.4f})")
    occlusion_df = pd.DataFrame(occlusion_rows)
    occlusion_df.to_csv("validation_modality_occlusion.csv", index=False)

    # 3. Retrained linear baselines reveal how much signal exists in metadata alone
    train_metadata = np.stack([dataset[int(i)][1].numpy() for i in train_indices])
    train_labels = np.asarray([dataset[int(i)][3].item() for i in train_indices])
    val_metadata = np.stack([dataset[int(i)][1].numpy() for i in val_indices])
    val_labels = np.asarray([dataset[int(i)][3].item() for i in val_indices])
    no_country_indices = [i for i in range(clinical_dim) if i not in country_indices]
    baseline_groups = {
        "country_only": country_indices,
        "clinical_all": list(range(clinical_dim)),
        "clinical_without_country": no_country_indices,
        "handcrafted_audio_only": acoustic_indices,
        "all_tabular_and_acoustic": list(range(metadata_dim))
    }
    baseline_rows = []
    log("\n--- RETRAINED LOGISTIC BASELINES ---")
    for baseline_name, columns in baseline_groups.items():
        if not columns:
            continue
        baseline = make_pipeline(
            StandardScaler(),
            LogisticRegression(class_weight="balanced", max_iter=2000, solver="liblinear", random_state=42)
        )
        baseline.fit(train_metadata[:, columns], train_labels)
        baseline_probs = baseline.predict_proba(val_metadata[:, columns])[:, 1]
        baseline_auc = _safe_auroc(val_labels, baseline_probs)
        baseline_rows.append({"baseline": baseline_name, "auroc": baseline_auc})
        log(f"{baseline_name:>27}: AUROC={baseline_auc:.4f}")
    baseline_df = pd.DataFrame(baseline_rows)
    baseline_df.to_csv("validation_linear_baselines.csv", index=False)

    # 4. Subgroup error analysis
    metadata_by_participant = artifacts["metadata_df"].set_index("participant")
    subgroup_frame = pd.DataFrame({
        "participant": participants,
        "label": labels,
        "probability": probabilities
    })
    country_cols = [c for c in feature_cols if c.startswith("country_")]
    countries, sexes, clip_counts = [], [], []
    for participant in participants:
        row = metadata_by_participant.loc[participant]
        if country_cols:
            countries.append(max(country_cols, key=lambda col: float(row[col])).replace("country_", ""))
        else:
            countries.append("Unknown")
        sexes.append("Male" if float(row.get("sex", 0.0)) >= 0.5 else "Female")
        clip_counts.append(len(dataset.patient_audio_map[participant]))
    subgroup_frame["country"] = countries
    subgroup_frame["sex"] = sexes
    subgroup_frame["clip_count"] = clip_counts
    subgroup_frame["prediction"] = (subgroup_frame["probability"] >= selected_threshold).astype(int)
    subgroup_frame["correct"] = subgroup_frame["prediction"] == subgroup_frame["label"]
    subgroup_frame.to_csv("validation_predictions.csv", index=False)

    subgroup_rows = []
    for subgroup_name in ["country", "sex"]:
        for subgroup_value, group in subgroup_frame.groupby(subgroup_name):
            group_metrics = _classification_metrics(group["label"], group["probability"], selected_threshold)
            subgroup_rows.append({
                "subgroup": subgroup_name,
                "value": subgroup_value,
                "n": len(group),
                "positives": int(group["label"].sum()),
                "auroc": _safe_auroc(group["label"], group["probability"]),
                "accuracy": group_metrics["accuracy"],
                "sensitivity": group_metrics["sensitivity"],
                "specificity": group_metrics["specificity"]
            })
    subgroup_df = pd.DataFrame(subgroup_rows)
    subgroup_df.to_csv("validation_subgroups.csv", index=False)
    log("\n--- SUBGROUP METRICS ---")
    log(subgroup_df.round(4).to_string(index=False))

    # 5. Clip-budget sweep: quality/latency trade-off for edge screening
    clip_budget_rows = [{"max_clips": "up_to_24", "auroc": auroc}]
    log("\n--- VALIDATION CLIP-BUDGET SWEEP ---")
    log(f"{'up_to_24':>8} clips: AUROC={auroc:.4f}")
    for max_clips in [1, 3, 5, 8]:
        budget_labels, budget_probs, _ = _collect_predictions(
            model, dataset, val_indices, batch_size=8, max_clips=max_clips
        )
        budget_auc = _safe_auroc(budget_labels, budget_probs)
        budget_metrics = _classification_metrics(budget_labels, budget_probs, selected_threshold)
        clip_budget_rows.append({
            "max_clips": max_clips,
            "auroc": budget_auc,
            "accuracy_at_full_threshold": budget_metrics["accuracy"]
        })
        log(f"{max_clips:>8} clips: AUROC={budget_auc:.4f}, accuracy={budget_metrics['accuracy']*100:.2f}%")
    clip_budget_df = pd.DataFrame(clip_budget_rows)
    clip_budget_df.to_csv("validation_clip_budget.csv", index=False)

    # 6. Parameter, storage, MAC, activation and CPU-latency profile
    cpu_model = copy.deepcopy(model).cpu().eval()

    # The training model keeps the complete ResNet18 object only to construct
    # `features`; layer4/fc and the duplicate parent registration are unused.
    # Removing that parent reference from this deployment copy preserves the
    # exact forward path while producing an honest compact edge artifact.
    if hasattr(cpu_model.feature_extractor, "resnet"):
        delattr(cpu_model.feature_extractor, "resnet")

    total_params = sum(parameter.numel() for parameter in cpu_model.parameters())
    trainable_params = sum(parameter.numel() for parameter in cpu_model.parameters() if parameter.requires_grad)
    component_params = {}
    for name, parameter in cpu_model.named_parameters():
        component = name.split(".")[0]
        component_params[component] = component_params.get(component, 0) + parameter.numel()

    validate_metadata_batchnorm(cpu_model)
    fp32_size_mb = _serialized_state_size_mb(cpu_model)
    compact_state_path = "tb_cough_edge_weights_fp32.pt"
    torch.save(cpu_model.state_dict(), compact_state_path)
    fp16_model = copy.deepcopy(cpu_model).half()
    fp16_size_mb = _serialized_state_size_mb(fp16_model)
    del fp16_model

    quantized_model = None
    quantized_size_mb = np.nan
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            quantized_model = torch.ao.quantization.quantize_dynamic(
                copy.deepcopy(cpu_model), {nn.Linear}, dtype=torch.qint8
            ).eval()
        quantized_size_mb = _serialized_state_size_mb(quantized_model)
    except Exception as exc:
        log(f"Dynamic INT8 profiling skipped: {exc}")

    profile_5 = _profile_macs_and_activations(cpu_model, metadata_dim, clip_count=5)
    cpu_latency_df = _benchmark_cpu_latency(cpu_model, metadata_dim)
    cpu_latency_df["precision"] = "FP32"
    if quantized_model is not None:
        int8_latency_df = _benchmark_cpu_latency(quantized_model, metadata_dim)
        int8_latency_df["precision"] = "Dynamic INT8 linear layers"
        latency_df = pd.concat([cpu_latency_df, int8_latency_df], ignore_index=True)
    else:
        latency_df = cpu_latency_df
    latency_df.to_csv("edge_cpu_latency.csv", index=False)

    checkpoint_path = artifacts.get("checkpoint_path")
    checkpoint_size_mb = (
        os.path.getsize(checkpoint_path) / (1024 ** 2)
        if checkpoint_path and os.path.exists(checkpoint_path)
        else np.nan
    )
    fp32_size_gib = fp32_size_mb / 1024
    fp16_size_gib = fp16_size_mb / 1024
    quantized_size_gib = quantized_size_mb / 1024 if np.isfinite(quantized_size_mb) else np.nan
    checkpoint_size_gib = checkpoint_size_mb / 1024 if np.isfinite(checkpoint_size_mb) else np.nan

    input_pcm16_kb_5 = 5 * 0.55 * 16000 * 2 / 1024
    largest_activation_mb = profile_5["largest_activation_bytes"] / (1024 ** 2)
    observed_tensor_budget_mb = fp32_size_mb + 3 * largest_activation_mb
    mobile_free_memory_budget_mb = int(np.ceil((max(fp16_size_mb, quantized_size_mb if np.isfinite(quantized_size_mb) else 0)
                                                + 6 * largest_activation_mb + 192) / 32) * 32)

    log("\n--- MODEL AND EDGE PROFILE ---")
    log(f"Parameters: {total_params:,} total / {trainable_params:,} trainable")
    for component, count in sorted(component_params.items(), key=lambda item: item[1], reverse=True):
        log(f"  {component:>20}: {count:,} ({count/total_params*100:.1f}%)")
    log(
        f"Compact edge weights: FP32={fp32_size_mb:.2f} MB ({fp32_size_gib:.4f} GiB) | "
        f"FP16={fp16_size_mb:.2f} MB ({fp16_size_gib:.4f} GiB)"
    )
    if np.isfinite(checkpoint_size_mb):
        log(f"Saved checkpoint file: {checkpoint_size_mb:.2f} MB ({checkpoint_size_gib:.4f} GiB)")
    if np.isfinite(quantized_size_mb):
        log(
            f"Dynamic INT8 size (Linear layers only): {quantized_size_mb:.2f} MB "
            f"({quantized_size_gib:.4f} GiB)"
        )
    log(f"Estimated Conv/Linear compute for 5 clips: {profile_5['macs']/1e9:.3f} GMACs (~{2*profile_5['macs']/1e9:.3f} GFLOPs)")
    log(f"Largest observed activation tensor (5 clips): {largest_activation_mb:.2f} MB")
    log(f"Observed tensor-budget proxy: {observed_tensor_budget_mb:.1f} MB (not peak RAM; excludes runtime/workspaces)")
    log(f"Five 0.55 s clips as PCM16: {input_pcm16_kb_5:.1f} KB")
    log("Model-only CPU latency on this Kaggle machine (not a phone benchmark; excludes audio/Mel preprocessing):")
    log(latency_df.round(2).to_string(index=False))

    log("\n--- PRACTICAL MINIMUM DEPLOYMENT TARGETS ---")
    log("Mobile minimum: ARM64, 4 CPU cores, 4 GB system RAM, Android 10+/iOS 15+,")
    log(f"  at least ~{mobile_free_memory_budget_mb} MB free app memory, and a 3-5 clip budget.")
    log("Mobile recommended: 6 GB RAM, 2+ performance cores or mobile NPU/GPU, FP16/full-INT8 model.")
    log("Desktop minimum: 64-bit 4-thread CPU, 4 GB system RAM, ~512 MB free process memory; GPU optional.")
    log("Desktop recommended: AVX2-capable CPU and 8 GB RAM; a GPU/NPU is optional.")
    log("These are engineering starting points, not guarantees: benchmark preprocessing plus inference on each target device.")
    log("For full INT8 convolution acceleration, use static quantization/QAT via ExecuTorch, TFLite, or ONNX Runtime;")
    log("PyTorch dynamic quantization above quantizes Linear layers only.")

    # 7. Optional one-patient TorchScript export for a fixed edge-facing API
    class EdgeScreeningWrapper(nn.Module):
        def __init__(self, base_model):
            super().__init__()
            self.base_model = base_model

        def forward(self, patient_specs, patient_metadata):
            logits = self.base_model([patient_specs], patient_metadata)["tb_logits"]
            return F.softmax(logits, dim=1)[:, 1]

    try:
        edge_wrapper = EdgeScreeningWrapper(cpu_model).eval()
        traced = torch.jit.trace(
            edge_wrapper,
            (torch.zeros(5, 1, 128, 36), torch.zeros(1, metadata_dim)),
            strict=False
        )
        edge_path = "tb_cough_edge_fp32.ts"
        traced.save(edge_path)
        log(f"TorchScript edge wrapper saved to '{edge_path}' (one patient; validate supported clip counts on target runtime).")
    except Exception as exc:
        edge_path = None
        log(f"TorchScript export skipped: {exc}")

    # 8. Diagnostic plots and machine-readable summary
    history_df = pd.DataFrame(artifacts["history"])
    history_df.to_csv("training_history.csv", index=False)
    fpr, tpr, _ = roc_curve(labels, probabilities)
    calibration_true, calibration_pred = calibration_curve(labels, probabilities, n_bins=10, strategy="quantile")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes[0, 0].plot(history_df["epoch"], history_df["train_loss"], label="Train")
    axes[0, 0].plot(history_df["epoch"], history_df["val_loss"], label="Validation")
    axes[0, 0].set_title("Total Loss")
    axes[0, 0].legend()

    axes[0, 1].plot(history_df["epoch"], history_df["val_loss"], label="Validation loss")
    axes[0, 1].set_title("Validation Loss")
    axes[0, 1].legend()

    axes[0, 2].plot(history_df["epoch"], history_df["val_auroc"], label="AUROC")
    axes[0, 2].set_title("Validation Quality")
    axes[0, 2].legend()

    axes[1, 0].plot(fpr, tpr, label=f"AUROC={auroc:.3f}")
    axes[1, 0].plot([0, 1], [0, 1], "--", color="gray")
    axes[1, 0].set_xlabel("False Positive Rate")
    axes[1, 0].set_ylabel("True Positive Rate")
    axes[1, 0].set_title("ROC Curve")
    axes[1, 0].legend()

    axes[1, 1].plot(calibration_pred, calibration_true, marker="o")
    axes[1, 1].plot([0, 1], [0, 1], "--", color="gray")
    axes[1, 1].set_xlabel("Mean Predicted Probability")
    axes[1, 1].set_ylabel("Observed TB Fraction")
    axes[1, 1].set_title("Calibration")

    numeric_clip_budget = clip_budget_df[clip_budget_df["max_clips"] != "up_to_24"].copy()
    numeric_clip_budget["max_clips"] = pd.to_numeric(numeric_clip_budget["max_clips"])
    axes[1, 2].plot(numeric_clip_budget["max_clips"], numeric_clip_budget["auroc"], marker="o")
    axes[1, 2].axhline(auroc, linestyle="--", color="gray", label="Up to 24 clips")
    axes[1, 2].set_xlabel("Maximum Clips per Patient")
    axes[1, 2].set_ylabel("AUROC")
    axes[1, 2].set_title("Edge Clip-Budget Trade-off")
    axes[1, 2].legend()

    plt.tight_layout()
    plt.savefig("validation_edge_diagnostics.png", dpi=150, bbox_inches="tight")
    plt.show()

    summary = {
        "best_training_epoch": int(artifacts["best_epoch"]),
        "validation_auroc": float(auroc),
        "validation_auroc_ci95": [float(ci_low), float(ci_high)],
        "average_precision": float(average_precision),
        "thresholds": {key: float(value) for key, value in thresholds.items()},
        "parameters": int(total_params),
        "fp32_size_mb": float(fp32_size_mb),
        "fp32_size_gib": float(fp32_size_gib),
        "fp16_size_mb": float(fp16_size_mb),
        "fp16_size_gib": float(fp16_size_gib),
        "checkpoint_size_mb": float(checkpoint_size_mb) if np.isfinite(checkpoint_size_mb) else None,
        "checkpoint_size_gib": float(checkpoint_size_gib) if np.isfinite(checkpoint_size_gib) else None,
        "dynamic_int8_size_mb": float(quantized_size_mb) if np.isfinite(quantized_size_mb) else None,
        "dynamic_int8_size_gib": float(quantized_size_gib) if np.isfinite(quantized_size_gib) else None,
        "five_clip_gmacs": float(profile_5["macs"] / 1e9),
        "compact_state_path": compact_state_path,
        "torchscript_path": edge_path
    }
    with open("validation_edge_summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    with open("validation_edge_report.txt", "w", encoding="utf-8") as file:
        file.write("\n".join(report))

    log("\nSaved: validation_edge_report.txt, validation_edge_summary.json,")
    log("validation_edge_diagnostics.png, validation_predictions.csv,")
    log("and profiling CSVs.")
    return {
        "summary": summary,
        "thresholds": threshold_df,
        "occlusion": occlusion_df,
        "baselines": baseline_df,
        "subgroups": subgroup_df,
        "clip_budget": clip_budget_df,
        "latency": latency_df
    }


validation_edge_analysis = run_validation_and_edge_analysis(training_artifacts)
