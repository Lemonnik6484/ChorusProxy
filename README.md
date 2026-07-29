# Chorus Proxy

A simple and lightweight minecraft-aware reverse proxy

## How it works

1. The program reads first packet (AKA Handshake) and reads the target domain
2. Searches for the corresponding `ip:port` in config
3. Redirects all the packets to the target `ip:port` without reading them 

## How to use

Make sure to have Python 3.10+ installed

Edit `config.json` to define the listen address and hostname routes:

```json
{
  "listen": {
    "host": "0.0.0.0",
    "port": 25565
  },
  "routes": {
    "mc.example.com": {
      "host": "192.168.1.10",
      "port": 25565
    }
  }
}
```

Then run:

```bash
python main.py
# or: python main.py --config /path/to/config.json
```

Use `Ctrl+C` to stop cleanly and wait for process to exit

## Mod/Plugin support

The proxy never modifies packets, so there will be no issues with mod/plugin support unless they do something with network