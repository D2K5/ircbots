import argparse
import asyncio
import glob
import os
import random
import re
import ssl

class IRCBot:
    def __init__(self, server, port, nickname, channel, chance, tls=False):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.channel = channel if channel.startswith('#') else f'#{channel}'
        self.chance = chance          # Float between 0.0 and 1.0 (e.g., 0.15 for 15%)
        self.tls = tls
        self.messages = []
        self.writer = None
        self.reader = None

    def load_messages(self):
        """Loads non-empty lines from all .txt files in the messages/ directory."""
        self.messages.clear()
        txt_files = glob.glob(os.path.join("messages", "*.txt"))
        
        if not txt_files:
            print("[!] Warning: No .txt files found in 'messages/' directory.")
            return

        for filepath in txt_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    self.messages.extend(lines)
            except Exception as e:
                print(f"[!] Error reading {filepath}: {e}")

        print(f"[+] Loaded {len(self.messages)} message(s) from {len(txt_files)} file(s).")

    async def send_raw(self, message):
        """Sends a raw IRC protocol message."""
        self.writer.write(f"{message}\r\n".encode("utf-8"))
        await self.writer.drain()

    async def send_channel_message(self, text):
        """Sends a PRIVMSG to the target channel."""
        await self.send_raw(f"PRIVMSG {self.channel} :{text}")
        print(f"[>] Sent to {self.channel}: {text}")

    def parse_privmsg(self, line):
        """
        Parses raw PRIVMSG lines to extract sender nick, target, and message content.
        Format: :nick!user@host PRIVMSG #channel :message text
        """
        match = re.match(r"^:([^!]+)![^ ]+\s+PRIVMSG\s+([^\s]+)\s+:(.*)$", line)
        if match:
            sender, target, text = match.groups()
            return sender, target, text
        return None, None, None

    async def handle_incoming(self):
        """Processes incoming lines from the IRC server."""
        while True:
            line = await self.reader.readline()
            if not line:
                print("[!] Connection lost.")
                break

            decoded = line.decode("utf-8", errors="ignore").strip()

            # Respond to server PING requests to maintain connection
            if decoded.startswith("PING"):
                server_id = decoded.split(" ", 1)[1]
                await self.send_raw(f"PONG {server_id}")
                continue

            # Process channel activity
            if "PRIVMSG" in decoded:
                sender, target, text = self.parse_privmsg(decoded)

                # Ignore messages sent by the bot itself or sent outside the target channel
                if sender and sender.lower() != self.nickname.lower() and target.lower() == self.channel.lower():
                    print(f"[<] {sender} in {self.channel}: {text}")
                    await self.evaluate_response_chance()

    async def evaluate_response_chance(self):
        """Rolls a probability check when someone chats."""
        if not self.messages:
            return

        roll = random.random()

        if roll < self.chance:
            selected_msg = random.choice(self.messages)
            # Pick a transformation: lowercase, uppercase, or unchanged
            transform = random.choice([str.lower, str.upper, lambda s: s])
            formatted_msg = transform(selected_msg)
            await self.send_channel_message(formatted_msg)

    async def run(self):
        self.load_messages()
        if not self.messages:
            print("[!] Cannot start without messages in 'messages/' directory.")
            return

        print(f"[*] Connecting to {self.server}:{self.port}...")
        ssl_ctx = ssl.create_default_context() if self.tls else None
        
        self.reader, self.writer = await asyncio.open_connection(
            self.server, self.port, ssl=ssl_ctx
        )

        # Standard IRC connection handshake
        await self.send_raw(f"NICK {self.nickname}")
        await self.send_raw(f"USER {self.nickname} 0 * :{self.nickname}")

        # Wait briefly for server registration before joining target channel
        await asyncio.sleep(3)
        await self.send_raw(f"JOIN {self.channel}")
        print(f"[+] Joined channel {self.channel}")

        # Continuous message handler loop
        await self.handle_incoming()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IRC Activity-Triggered Message Bot")
    parser.add_argument("--server", required=True, help="IRC server address (e.g., irc.libera.chat)")
    parser.add_argument("--port", type=int, default=6667, help="IRC port (default: 6667)")
    parser.add_argument("--nick", default="ChatBot", help="Bot nickname (default: ChatBot)")
    parser.add_argument("--channel", required=True, help="Channel to join (e.g., #mychannel)")
    parser.add_argument("--chance", type=float, default=0.2, help="Probability of replying when someone chats (0.0 to 1.0, default: 0.2)")
    parser.add_argument("--tls", action="store_true", help="Use TLS/SSL connection")

    args = parser.parse_args()

    bot = IRCBot(
        server=args.server,
        port=args.port,
        nickname=args.nick,
        channel=args.channel,
        chance=args.chance,
        tls=args.tls
    )

    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n[*] Bot stopped.")
