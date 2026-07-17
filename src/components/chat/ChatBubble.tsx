import { ChatMessage } from "@/models/chat";

export function ChatBubble({ message }: { message: ChatMessage }) {
  return (
    <div className={`chat-bubble chat-bubble--${message.role}`}>
      <p>{message.content}</p>
    </div>
  );
}
