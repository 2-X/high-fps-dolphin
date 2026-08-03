# high-fps-dolphin — Super Mario Sunshine high-FPS project

Everything lives in **[sunshine/README.md](sunshine/README.md)** — read that first.
It has the full state, the Gecko codes, the address map, PC import steps, and the 360Hz roadmap.

Two dependencies are NOT vendored here (reproduce on the PC):

```bash
# custom Dolphin (required for correct audio at high fps)
git clone https://github.com/dolphin-emu/dolphin
cd dolphin && git checkout $(cut -d' ' -f1 ../sunshine/dolphin-patches/UPSTREAM_COMMIT.txt)
git apply ../sunshine/dolphin-patches/high-fps-dolphin.patch

# SMS decomp (JP) — research reference
git clone https://github.com/doldecomp/sms
```

Texture pack zips are gitignored (GitHub 100MB limit) — transfer `sunshine/textures/*.zip` by direct copy.
