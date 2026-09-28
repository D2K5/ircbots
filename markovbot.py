#!/usr/bin/env python3
import argparse
import random
import re
import socket
import ssl
import sys
import threading
import time
from collections import Counter, defaultdict

class MarkovBrain:

  def __init__(
      self,
      brain_file="brain_file.txt",
      min_order=2,
      max_order=3,
      debug=False,
      flatten=False,
      max_weight=5,
  ):
    self.brain_file = brain_file
    self.min_order = min_order
    self.max_order = max_order
    self.debug = debug
    self.flatten = flatten
    self.max_weight = max_weight
    self.START = "^B"
    self.END = "^C"

    # Initialize chain dictionary dynamically up to max_order
    self.chains = {
        order: defaultdict(Counter)
        for order in range(1, self.max_order + 1)
    }
    self.all_words = set()
    self.load_brain()

  def log(self, msg):
    if self.debug:
      print(f"[DEBUG] {msg}")

  def get_stats(self):
    """Calculates memory metrics across all Markov orders."""
    total_contexts = sum(len(self.chains[o]) for o in self.chains)
    total_transitions = sum(
        sum(len(counter) for counter in self.chains[o].values())
        for o in self.chains
    )
    return {
        "words": len(self.all_words),
        "contexts": total_contexts,
        "transitions": total_transitions,
    }

  def load_brain(self):
    """Loads and parses the brain file into N-order chains."""
    for o in self.chains:
      self.chains[o].clear()
    self.all_words.clear()

    line_count = 0
    try:
      with open(
          self.brain_file, "r", encoding="utf-8", errors="replace"
      ) as f:
        for line in f:
          line = line.strip()
          if not line:
            continue

          parts = re.split(r"\t+|\s{2,}", line)
          if not parts[0].isdigit():
            continue

          count = int(parts[0])
          tokens = parts[1:]

          if not tokens:
            continue

          line_count += 1
          for token in tokens:
            if token not in (self.START, self.END, "^C", "^B"):
              self.all_words.add(token)

          if len(tokens) == 1:
            self.chains[1][(self.START,)][tokens[0]] += count
          elif len(tokens) == 2:
            w1, w2 = tokens[0], tokens[1]
            self.chains[1][(w1,)][w2] += count
          else:
            for o in range(1, min(len(tokens), self.max_order + 1)):
              ctx = tuple(tokens[:o])
              nxt = tokens[o] if o < len(tokens) else self.END
              self.chains[o][ctx][nxt] += count

      stats = self.get_stats()
      print(
          f"[*] Loaded brain from '{self.brain_file}' ({line_count} lines"
          f" processed)."
      )
      print(
          f"[*] Brain Stats -> Vocabulary: {stats['words']} words | Contexts:"
          f" {stats['contexts']} | Transitions: {stats['transitions']}"
      )
    except FileNotFoundError:
      print(f"[!] '{self.brain_file}' not found. Starting with empty brain.")

  def learn(self, text):
    """Learns new sentence transitions from incoming chat text and logs metrics."""
    tokens = [w for w in text.strip().split() if w]
    if not tokens:
      return

    for token in tokens:
      self.all_words.add(token)

    def capped_add(chain_dict, key, next_word):
      if chain_dict[key][next_word] < self.max_weight:
        chain_dict[key][next_word] += 1

    capped_add(self.chains[1], (self.START,), tokens[0])

    for o in range(1, self.max_order + 1):
      for i in range(len(tokens) - o):
        ctx = tuple(tokens[i : i + o])
        nxt = tokens[i + o]
        capped_add(self.chains[o], ctx, nxt)

    for o in range(1, min(len(tokens), self.max_order) + 1):
      ctx = tuple(tokens[-o:])
      capped_add(self.chains[o], ctx, self.END)

    # Output stats line for learned text
    stats = self.get_stats()
    print(
        f"[LEARNED] Tokens: {len(tokens)} | Brain Totals -> Words:"
        f" {stats['words']} | Contexts: {stats['contexts']} | Transitions:"
        f" {stats['transitions']}"
    )

    try:
      with open(self.brain_file, "a", encoding="utf-8") as f:
        f.write(f"1\t{self.START}\t{tokens[0]}\n")
        for i in range(len(tokens) - 1):
          f.write(f"1\t{tokens[i]}\t{tokens[i+1]}\n")
          if i < len(tokens) - 2:
            f.write(f"1\t{tokens[i]}\t{tokens[i+1]}\t{tokens[i+2]}\n")
        f.write(f"1\t{tokens[-1]}\t{self.END}\n")
    except Exception as e:
      print(f"[!] Error saving to brain file: {e}")

  def get_historical_seed(self, user_words):
    """Finds words in user input matching historical brain vocabulary."""
    valid_seeds = [w for w in user_words if w in self.all_words]
    if valid_seeds:
      chosen = random.choice(valid_seeds)
      self.log(f"Matched seed word '{chosen}' from user input in database.")
      return [chosen]
    return None

  def _sample(self, counter, temperature=1.4):
    """Samples next word with flatten and max_weight controls."""
    if not counter:
      return None

    words = list(counter.keys())

    if self.flatten:
      self.log("Flatten option active: uniform selection across options.")
      return random.choice(words)

    counts = [min(c, self.max_weight) for c in counter.values()]

    if temperature != 1.0:
      weights = [c ** (1.0 / temperature) for c in counts]
    else:
      weights = counts

    total = sum(weights)
    if total <= 0:
      return random.choice(words)

    r = random.uniform(0, total)
    upto = 0.0
    for w, weight in zip(words, weights):
      if upto + weight >= r:
        return w
      upto += weight

    return words[-1]

  def _step(self, context, temperature=1.4):
    """Steps through higher to lower Markov order chains."""
    for order in range(self.max_order, 0, -1):
      if len(context) >= order:
        key = tuple(context[-order:])
        counter = self.chains[order].get(key)
        if counter:
          nxt = self._sample(counter, temperature=temperature)
          self.log(
              f"Order {order} match for context {key} -> selected '{nxt}'"
          )
          if nxt and nxt not in (self.END, "^C"):
            return nxt
          elif order == 1:
            return nxt
        else:
          self.log(f"Order {order} miss for context {key}")

    return None

  def generate(
      self,
      seed_words=None,
      max_words=20,
      min_words=1,
      temperature=1.4,
      short_reply_chance=0.15,
      prompt_text="",
  ):
    """Generates a text sequence while logging sampling telemetry."""
    stats = self.get_stats()
    self.log(
        f"Starting Generation | Database -> Words: {stats['words']} | Contexts:"
        f" {stats['contexts']}"
    )

    for attempt_try in range(5):
      out = []
      if seed_words:
        out = [w for w in seed_words if w not in (self.START, self.END, "^C")]
        self.log(f"Attempt {attempt_try+1}: Seeding with {out}")

      if not out:
        start_counter = self.chains[1].get((self.START,))
        if not start_counter:
          return ""
        first_word = self._sample(start_counter, temperature=temperature)
        if not first_word or first_word in (self.END, "^C"):
          return ""
        out = [first_word]
        self.log(f"Attempt {attempt_try+1}: Random start word '{first_word}'")

      attempts = 0
      while len(out) < max_words and attempts < 100:
        attempts += 1
        nxt = self._step(out, temperature=temperature)

        if nxt is None or nxt in (self.END, "^C"):
          if len(out) < 3 and len(out) >= min_words:
            if random.random() < short_reply_chance:
              self.log("Short reply accepted.")
              break
            else:
              self.log("Short reply rejected. Retrying step...")
              continue
          elif len(out) >= min_words:
            break
          else:
            continue

        out.append(nxt)

      result = " ".join(out)

      # Reject verbatim copies of prompt input
      if (
          prompt_text
          and result.strip().lower() == prompt_text.strip().lower()
      ):
        self.log(
            f"Generated text '{result}' matches input prompt. Retrying"
            " unseeded..."
        )
        seed_words = None
        continue

      print(
          f"[OUTPUT INFO] Generated {len(out)} words using database of"
          f" {stats['contexts']} contexts."
      )
      return result

    return ""


class IRCBot:

  def __init__(self, args):
    self.args = args
    self.brain = MarkovBrain(
        brain_file=args.brain,
        min_order=args.order,
        max_order=args.max_order,
        debug=args.debug,
        flatten=args.flatten,
        max_weight=args.max_weight,
    )
    self.sock = None
    self.running = True

  def connect(self):
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if self.args.use_ssl:
      ctx = ssl.create_default_context()
      ctx.check_hostname = False
      ctx.verify_mode = ssl.CERT_NONE
      self.sock = ctx.wrap_socket(raw_sock, server_hostname=self.args.server)
    else:
      self.sock = raw_sock

    self.sock.connect((self.args.server, self.args.port))
    self.send_raw(f"NICK {self.args.nick}")
    self.send_raw(f"USER {self.args.nick} 0 * :{self.args.nick}")

  def send_raw(self, msg):
    if self.args.debug:
      print(f"[RAW OUT] {msg}")
    self.sock.send(f"{msg}\r\n".encode("utf-8"))

  def send_privmsg(self, target, msg):
    if msg and msg.strip():
      self.send_raw(f"PRIVMSG {target} :{msg}")

  def interval_chatter_loop(self):
    if self.args.interval <= 0:
      print("[*] Timer chatter disabled (--interval 0).")
      return

    while self.running:
      time.sleep(self.args.interval)
      response = self.brain.generate(temperature=self.args.temp)
      if response:
        print(f"[Timer Chatter] -> {response}")
        self.send_privmsg(self.args.channel, response)

  def run(self):
    self.connect()

    if self.args.interval > 0:
      timer_thread = threading.Thread(
          target=self.interval_chatter_loop, daemon=True
      )
      timer_thread.start()

    buffer = ""
    while self.running:
      try:
        data = self.sock.recv(2048).decode("utf-8", errors="replace")
        if not data:
          break
      except socket.error:
        break

      buffer += data
      lines = buffer.split("\r\n")
      buffer = lines.pop()

      for line in lines:
        if self.args.debug:
          print(f"[RAW IN] {line}")
        else:
          print(f"[IRC] {line}")

        if line.startswith("PING"):
          self.send_raw(f"PONG {line.split()[1]}")
          continue

        parts = line.split()
        if len(parts) > 1 and parts[1] in ("001", "376"):
          self.send_raw(f"JOIN {self.args.channel}")
          continue

        if "PRIVMSG" in line:
          match = re.match(r"^:([^!]+)![^@]+@\S+ PRIVMSG (\S+) :(.*)$", line)
          if match:
            nick, target, text = match.groups()

            if nick.lower() == self.args.nick.lower():
              continue

            clean_text = re.sub(
                r"[\x02\x0F\x16\x1D\x1F]|\x03\d{0,2}(,\d{0,2})?", "", text
            ).strip()

            # Learn line and print statistics
            self.brain.learn(clean_text)

            is_addressed = self.args.nick.lower() in clean_text.lower()
            if is_addressed or random.random() < self.args.chance:
              words = clean_text.split()

              seed = None
              if words and self.args.use_seed:
                seed = self.brain.get_historical_seed(words)

              reply = self.brain.generate(
                  seed_words=seed,
                  temperature=self.args.temp,
                  prompt_text=clean_text,
              )
              if reply:
                print(f"[Triggered Reply] -> {reply}")
                self.send_privmsg(self.args.channel, reply)


def parse_args():
  parser = argparse.ArgumentParser(
      description="Markov Chain IRC Bot with Statistics Telemetry"
  )
  parser.add_argument(
      "--server",
      default="127.0.0.1",
      help="IRC server IP/hostname (default: 127.0.0.1)",
  )
  parser.add_argument(
      "--port", type=int, default=6667, help="IRC server port (default: 6667)"
  )
  parser.add_argument(
      "--nick", default="MarkovTest", help="Bot nickname (default: MarkovTest)"
  )
  parser.add_argument(
      "--channel", default="#bot", help="Channel to join (default: #bot)"
  )
  parser.add_argument(
      "--brain",
      default="brain_file.txt",
      help="Path to brain file (default: brain_file.txt)",
  )
  parser.add_argument(
      "--chance",
      type=float,
      default=0.4,
      help="Probability to respond to chatter (0.0 - 1.0)",
  )
  parser.add_argument(
      "--interval",
      type=int,
      default=0,
      help="Periodic chatter interval in seconds (0 = disabled)",
  )
  parser.add_argument(
      "--order",
      type=int,
      default=2,
      help="Minimum Markov order context (default: 2)",
  )
  parser.add_argument(
      "--max-order",
      type=int,
      default=3,
      help="Maximum Markov order context (default: 3)",
  )
  parser.add_argument(
      "--temp",
      type=float,
      default=1.4,
      help="Sampling temperature (default: 1.4)",
  )
  parser.add_argument(
      "--max-weight",
      type=int,
      default=5,
      help="Cap max frequency count for any token transition (default: 5)",
  )
  parser.add_argument(
      "--flatten",
      action="store_true",
      help="Sample transition paths with equal probability regardless of count",
  )
  parser.add_argument(
      "--use-ssl", action="store_true", help="Enable SSL connection"
  )
  parser.add_argument(
      "--use-seed",
      action="store_true",
      help="Seed responses using historical vocabulary from user prompt",
  )
  parser.add_argument(
      "--debug",
      action="store_true",
      help="Enable verbose debugging logs in terminal",
  )
  return parser.parse_args()


if __name__ == "__main__":
  args = parse_args()
  bot = IRCBot(args)
  try:
    bot.run()
  except KeyboardInterrupt:
    print("\n[*] KeyboardInterrupt detected. Shutting down bot gracefully...")
    sys.exit(0)
