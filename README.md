# geoguessr-avatar

Fetch GeoGuessr avatars and render them as still PNGs in any animation pose: a player's
own win animation (including purchased ones with props, like the office chair), the
built-in lose poses, taunts, idles and more.

Built for things like daily-challenge podium images in community bots.

> Unofficial. Not affiliated with or endorsed by GeoGuessr. This uses undocumented
> endpoints of geoguessr.com that can change at any time. Avatar assets belong to
> GeoGuessr; this package downloads them on demand and does not redistribute them.

## How it works

GeoGuessr has no "posed avatar" image. The site draws avatars live in three.js. This
package does the same thing in headless Chromium (via Playwright):

1. reads the player's equipped items from the public avatar API,
2. downloads the meshes, textures and animation clips (cached on disk),
3. assembles the avatar the way the site does: clothing re-bound to one skeleton,
   morph targets (hats squashing hair), hidden slots, face expressions, held items,
4. jumps to the requested moment of the clip and renders it with a toon shader that
   matches the site's look.

No login or `_ncfa` cookie is needed.

## Install

```sh
pip install geoguessr-avatar      # or: uv add geoguessr-avatar
playwright install chromium       # one-time browser download
```

On a Linux server: `playwright install --with-deps --only-shell chromium`. Rendering uses
SwiftShader (software WebGL) by default, so no GPU is required.

## Usage

The user ID is the hex string in a profile URL: `geoguessr.com/user/<user-id>`.

### Plain (synchronous) code

```python
from geoguessr_avatar import SyncAvatarRenderer

renderer = SyncAvatarRenderer()  # starts Chromium; create once and reuse

# The player's own win animation (or the default WIN), held 1 s before its end.
renderer.render("<user-id>").save("win.png")

# Any built-in clip, at a moment of your choice.
renderer.render("<user-id>", "LOSE_KNEES", progress=0.5).save("knees.png")

# Or by seconds, and any win-animation asset by ID.
chair = renderer.render("<user-id>", "WINANIMATION_HERMANMILLER_XZNC", time=3.0)
png_bytes = chair.png  # ready to upload or paste into a bigger image

renderer.close()  # or use it as a context manager: `with SyncAvatarRenderer() as renderer:`
```

`SyncAvatarRenderer` runs its own event loop on a background thread, so it is safe to call
from several threads, and from inside async code too. `render()` takes a `timeout`
(default 120 s).

Starting Chromium takes about a second. After that, a render takes about 0.5–1 s. For a
one-off script, `render_avatar("<user-id>", "WIN_FLIP_JUMP")` does both in one call.

### asyncio

```python
from geoguessr_avatar import AvatarRenderer

async with AvatarRenderer() as renderer:
    result = await renderer.render("<user-id>", "LOSE_KNEES", progress=0.5)
```

Both renderers take the same `render()` arguments.

### Options

| Parameter | Default | Meaning |
|---|---|---|
| `animation` | `None` | `None`: the player's equipped win animation, else `WIN`. A built-in name (see below), or an animation asset ID / `AvatarItem`. |
| `time` / `progress` | 1 s before end | Moment to render, in seconds or 0.0–1.0. Clamped to the clip. |
| `width`, `height` | `1080`, `1440` | Output size. The default matches GeoGuessr's own full-body image. |
| `framing` | `"fixed"` | `"fixed"`: one camera for everyone, identical to GeoGuessr's full-body image. `"fit"`: crop tightly to the posed avatar. |
| `zoom` | `1.0` | Fixed framing only. Use `0.85` for headroom: tall hats and jumps are cropped at `1.0`, just like on the site. |
| `background` | `None` | Hex colour, or transparent. |
| `supersample` | `2.0` | Render scale before downsampling (anti-aliasing). |

`RenderResult` has `.png` (bytes), `.save(path)`, `.animation`, `.time`, `.duration` and
`.bounds`.

### Built-in animations

```
win:   WIN WIN_BALLERINA WIN_FINGERGUNS WIN_FLIP_JUMP WIN_KAWAII WIN_MEDITATION
       WIN_RAISE_THE_ROOF WIN_WAVE CELEBRATE
lose:  LOSE LOSE_CROSSED_ARMS LOSE_JAWDROP LOSE_KNEES LOSE_SAGGING LOSE_SITTING
       LOSE_SWING_FIST UPSET UPSET_MORE
taunt: TAUNT_BOXER TAUNT_COME_AT_ME TAUNT_CRANE_KICK TAUNT_EYES_ON_YOU TAUNT_OBJECTION
idle:  IDLE IDLE_EAGER IDLE_CROSSED IDLE_ARMS_CROSSED IDLE_ARMS_SIDES IDLE_DISCIPLINED
       IDLE_RELAXED IDLE_RESTING_ARM
other: SECOND_WIND SLEEP ENERGY_BOOST OK_GUESS PING_HEAD PING_LOWER PING_UPPER BADGE_SHOW
       BADGE_SHOW_IDLE SELECT EMOTE_HELLO GAMING GAMING_WAITING BALANCE_LEFT BALANCE_RIGHT
       BALANCE_RUN BALANCE_RUN_BACK
```

Players can only customise their **win** animation (equipment slot 12). Everything else is
shared by all players, so for "losing" poses your code picks the clip.

### Podium example

[`examples/podium.py`](examples/podium.py) renders the top three on a podium: the winner in
their own win animation, the others in a built-in pose.

```sh
uv run --with pillow examples/podium.py <first-id> <second-id> <third-id> -o podium.png
```

### Data only

```python
from geoguessr_avatar import GeoGuessrClient, Slot

async with GeoGuessrClient() as gg:
    avatar = await gg.get_avatar("<user-id>")
    print([i.id for i in avatar.items], avatar.win_animation)
    hair_glb = await gg.asset(avatar.item(Slot.HAIR).mesh_glb)  # raw .glb bytes
    static_png = await gg.full_body_png("<user-id>")  # GeoGuessr's own render
```

### Command line

```sh
geoguessr-avatar render <user-id> -a LOSE_KNEES -p 0.5 -o knees.png
geoguessr-avatar render <user-id> --zoom 0.85 --background '#1d1b2e'
geoguessr-avatar info <user-id>        # equipped items and win animation
geoguessr-avatar animations            # list built-in clips
```

### Docker

```sh
docker build -t geoguessr-avatar .
docker run --rm -v "$PWD:/out" geoguessr-avatar render <user-id> -o /out/win.png
```

## Caching

Downloaded files are cached in `$XDG_CACHE_HOME/geoguessr-avatar` (default
`~/.cache/geoguessr-avatar`). Content-hashed assets are kept forever, and built-in
animation clips are re-checked weekly. Pass `GeoGuessrClient(cache_dir=...)` to change it.
Avatar loadouts are always fetched fresh.

## Endpoints used

| Data | Endpoint |
|---|---|
| Equipped items | `GET /api/v4/avatar/user/{userId}` |
| Asset lookup by ID | `GET /api/v4/avatar/assets?ids=...` |
| Meshes, textures, win-animation clips | `https://www.geoguessr.com/assets/{path}` |
| Built-in clips, head | `/static/avatar-assets/animations/{NAME}.glb`, `/static/avatar-assets/head/head.glb` |
| Profile, full-body image | `GET /api/v3/users/{userId}`, `/images/plain/{path}` |

## Limitations

- Still frames only. For animation output, render several frames and assemble them yourself.
- Club-branded clothing renders with its base texture, without the club logo.
- Companions (pets), badges and emote bubbles are not drawn.
- The idle eye-blink is random on the site and not reproduced.

## Development

```sh
uv sync
uv run playwright install chromium
uv run pytest                                          # offline tests
GEOGUESSR_AVATAR_NETWORK_TESTS=1 uv run pytest         # + live site and Chromium
uv run ruff check . && uv run ruff format --check .
```

`src/geoguessr_avatar/web/vendor/` holds three.js r185 (MIT, see `three-LICENSE`), the
version geoguessr.com uses, plus its Draco decoder.

## Releasing

1. Bump `version` in `pyproject.toml` and commit.
2. Create a GitHub release with a tag like `v0.1.0`. The `Publish to PyPI` workflow builds
   the package and uploads it.

## License

MIT
