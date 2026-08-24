# Build SuaraNafas dari lokasi network share (UNC).
#
# Next.js 16 + Turbopack tidak dapat mem-build langsung dari path UNC:
#   1) realpath Windows mengubah semua file network ke bentuk \\?\UNC\... sehingga
#      dianggap "di luar root directory" saat Tailwind memindai source.
#   2) Sebaliknya, jika root di-set ke bentuk \\?\UNC\, emitter Turbopack
#      gagal menulis artefak build.
#   3) Mode webpack juga tidak lagi didukung penuh oleh Next 16.
#
# Skrip ini membuat salinan build sementara di disk lokal (bukan memindahkan
# proyek), menjalankan `next build` di sana, lalu melaporkan hasilnya.

param(
    [switch]$OpenFolder
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$shadowRoot = Join-Path $env:LOCALAPPDATA "SuaraNafas\build-shadow"

function Write-Step([string]$message) {
    Write-Host ""
    Write-Host "==> $message" -ForegroundColor Cyan
}

Write-Step "Proyek sumber: $projectRoot"
Write-Step "Lokasi build lokal: $shadowRoot"

New-Item -ItemType Directory -Path $shadowRoot -Force | Out-Null

Write-Step "Menyalin berkas sumber (robocopy /MIR, inkremental)"

$copyItems = @(
    @{ Source = "src"; Target = "src" },
    @{ Source = "public"; Target = "public" }
)

foreach ($item in $copyItems) {
    robocopy (Join-Path $projectRoot $item.Source) `
             (Join-Path $shadowRoot $item.Target) `
             /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy gagal untuk $($item.Source) dengan kode $LASTEXITCODE"
    }
}

$rootFiles = @(
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "eslint.config.mjs",
    "postcss.config.mjs",
    "next.config.ts"
)

foreach ($file in $rootFiles) {
    $source = Join-Path $projectRoot $file
    if (Test-Path -LiteralPath $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $shadowRoot $file) -Force
    }
}

foreach ($stale in @(".gitignore", "README.md")) {
    $target = Join-Path $shadowRoot $stale
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
}

Write-Step "Menyiapkan dependensi node_modules"

$lockSource = Get-Item -LiteralPath (Join-Path $projectRoot "package-lock.json")
$lockShadow = Join-Path $shadowRoot "package-lock.json"
$stampFile = Join-Path $shadowRoot ".lock-stamp"
$needsInstall = -not (Test-Path (Join-Path $shadowRoot "node_modules"))

if (-not $needsInstall -and (Test-Path $stampFile)) {
    $previousStamp = Get-Content $stampFile -ErrorAction SilentlyContinue
    if ($previousStamp -ne $lockSource.LastWriteTimeUtc.Ticks) {
        $needsInstall = $true
    }
} else {
    $needsInstall = $true
}

if ($needsInstall) {
    Write-Host "    npm install berjalan (cache lokal membuatnya cepat)..."
    Push-Location $shadowRoot
    try {
        cmd /c "npm install --no-audit --no-fund"
        if ($LASTEXITCODE -ne 0) { throw "npm install gagal" }
    } finally {
        Pop-Location
    }
}
Set-Content -Path $stampFile -Value $lockSource.LastWriteTimeUtc.Ticks

Write-Step "Membersihkan .next lama"

$nextDir = Join-Path $shadowRoot ".next"
if (Test-Path $nextDir) { Remove-Item -Recurse -Force $nextDir }

Write-Step "Menjalankan next build (Turbopack) di disk lokal"

Push-Location $shadowRoot
try {
    & node "node_modules/next/dist/bin/next" build
    $buildExit = $LASTEXITCODE
} finally {
    Pop-Location
}

if ($buildExit -ne 0) {
    Write-Host ""
    Write-Host "Build GAGAL (kode $buildExit). Log ada di atas." -ForegroundColor Red
    exit $buildExit
}

Write-Host ""
Write-Host "Build SUKSES." -ForegroundColor Green
Write-Host "Hasil build: $nextDir"
Write-Host "Catatan: .next tetap di lokasi lokal karena Turbopack tidak dapat"
Write-Host "menulis artefak langsung ke network share."
Write-Host "Untuk preview production: cd '$shadowRoot' lalu 'npm run start'."

if ($OpenFolder) {
    Start-Process explorer.exe -ArgumentList $shadowRoot
}
