# running

### markov:

```sh
python3 markovbot.py --server 127.0.0.1 --port 6667 --nick Markov --channel '#bot' --brain brain_file.txt --chance 0.05 --interval 0 --order 2 --max-order 2 --temp 1.2
```

### text bot:

```sh
python3 textbot.py --nick Text --server 127.0.0.1 --port 6667 --channel "#bot" --chance 0.02
```
