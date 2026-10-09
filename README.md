# geoguessr-avatar

Render any GeoGuessr player's 3D avatar as a PNG, in any animation pose: their own win
animation (including purchased ones with props, like the office chair), lose poses, taunts,
idles and more. Built for things like daily-challenge podium images in community bots.
You can also export the avatar itself as an animated 3D model (`.glb`).

![One avatar in six poses](https://raw.githubusercontent.com/vonkoro/geoguessr-avatar/main/docs/hero.png)

> Unofficial. Not affiliated with or endorsed by GeoGuessr. It uses undocumented
> geoguessr.com endpoints, which can change at any time. Avatar assets belong to
> GeoGuessr; this package downloads them on demand and does not redistribute them.

## Quick start

```sh
pip install geoguessr-avatar
playwright install chromium          # one-time download of the browser used for rendering

geoguessr-avatar render 656461a8a02239a1b6a4482e -a LOSE_KNEES -o knees.png
```

That's a real player (thanks, Felix), so the command works as-is. Swap in anyone's user ID,
or paste their profile URL: `https://www.geoguessr.com/user/<user-id>`.

From Python:

```python
from geoguessr_avatar import SyncAvatarRenderer

with SyncAvatarRenderer() as renderer:
    renderer.render("656461a8a02239a1b6a4482e").save("win.png")  # their own win animation
    renderer.render("656461a8a02239a1b6a4482e", "LOSE_KNEES").save("knees.png")
```

No login, API key or GeoGuessr cookie is needed.

## Using it in your code

Create one renderer when your program starts and reuse it. Starting the browser takes
about a second, and each render after that takes about 0.5–1 s.

```python
from geoguessr_avatar import SyncAvatarRenderer

renderer = SyncAvatarRenderer()

result = renderer.render(user_id, "LOSE_KNEES", progress=0.5)
result.png  # PNG bytes: save, upload, or paste into a bigger image
result.save("knees.png")

renderer.close()  # when your program shuts down
```

`SyncAvatarRenderer` is safe to call from several threads, and from inside async code.

If your code is `async`, use `AvatarRenderer`. It takes exactly the same arguments:

```python
from geoguessr_avatar import AvatarRenderer

async with AvatarRenderer() as renderer:
    result = await renderer.render(user_id, "LOSE_KNEES", progress=0.5)
```

For a one-off script, `render_avatar(user_id, "LOSE_KNEES")` starts a browser, renders
and closes in one call.

## Choosing the animation

| `animation=` | What you get |
|---|---|
| *(omitted)* | The player's equipped win animation. Players without one get the default `WIN`. |
| a built-in name, e.g. `"LOSE_KNEES"` | The same clip for everyone. See the gallery below. |
| a win-animation asset ID, e.g. `"WINANIMATION_HERMANMILLER_XZNC"` | Any purchasable win animation, on any player. |

Players can only customise their **win** animation. All the lose, taunt and idle clips are
shared, so for "losing" poses your code picks the clip.

To see a player's items and the ID of their win animation:

```sh
geoguessr-avatar info 656461a8a02239a1b6a4482e
```

### Built-in animations

Shown at the default frame (see the next section). `geoguessr-avatar animations` prints the
same list.

![Every built-in animation](https://raw.githubusercontent.com/vonkoro/geoguessr-avatar/main/docs/animations.png)

## Choosing the moment

An animation is a few seconds long, so you pick which moment becomes the picture:

- `time=2.5`: seconds from the start.
- `progress=0.5`: halfway; 0.0 is the start and 1.0 the end.
- Neither: 1 second before the end, the frame GeoGuessr itself holds a pose on.

Many clips start and end in a neutral stance. If the default frame looks plain, try a few
`progress` values; the CLI makes that quick:

```sh
for p in 0.2 0.4 0.6 0.8; do geoguessr-avatar render <user> -a LOSE_SAGGING -p $p -o sag_$p.png; done
```

## Size and framing

The default output is a 1080×1440 PNG with a transparent background, framed exactly like
GeoGuessr's own full-body image.

| Option | Default | What it does |
|---|---|---|
| `width`, `height` | `1080`, `1440` | Output size in pixels. |
| `framing` | `"fixed"` | `"fixed"`: the same camera for every player and pose, so everyone has the same scale. `"fit"`: crop tightly around the posed avatar. |
| `zoom` | `1.0` | Fixed framing only. `0.85` leaves headroom: tall hats and jumps get cropped at `1.0`, just like on the site. |
| `margin` | `0.04` | Fit framing only: empty space around the avatar. |
| `background` | `None` | A hex colour such as `"#1d1b2e"`, or `None` for transparent. |
| `supersample` | `2.0` | Anti-aliasing quality. Higher is smoother and slower. |
| `timeout` | `120` | `SyncAvatarRenderer` only: seconds before giving up. |

A few clips move the avatar sideways (e.g. `WIN_FLIP_JUMP`) and can leave a fixed frame. Use
`framing="fit"` for those.

## 3D models

`export_model` gives you the avatar itself instead of a picture: a `.glb` (binary glTF) file
with the textured avatar on its skeleton, which 3D tools, game engines and web viewers can open.

```python
from geoguessr_avatar import SyncAvatarRenderer

with SyncAvatarRenderer() as renderer:
    renderer.export_model("656461a8a02239a1b6a4482e").save("avatar.glb")
    renderer.export_model("656461a8a02239a1b6a4482e", "TAUNT_BOXER", progress=0.4).save("boxer.glb")
```

```sh
geoguessr-avatar model 656461a8a02239a1b6a4482e -a TAUNT_BOXER -o boxer.glb
```

It takes the same `animation`, `time` and `progress` as `render`. The model is posed at that
moment, and the whole clip is included as well, so a viewer that plays animations plays it,
props and all. Expect a few MB per file.

Compared with the PNG renders:

- glTF can't store GeoGuessr's toon shading, so the model uses plain matte materials and
  takes on the lighting of whatever displays it.
- The face expression stays the one at the chosen moment for the whole animation.

## Recipes

**Podium.** [`examples/podium.py`](https://github.com/vonkoro/geoguessr-avatar/blob/main/examples/podium.py) puts the top three on a podium: the
winner in their own win animation, the others in a built-in pose. It needs Pillow
(`pip install pillow`).

```sh
python examples/podium.py <first-id> <second-id> <third-id> -o podium.png
```

**Sending to a chat.** Apps that recompress photos (Telegram's `sendPhoto`, for example)
lose the transparency. Either pass `background="#..."`, or paste the PNG onto your own
image first.

**Just the data, no rendering:**

```python
import asyncio
from geoguessr_avatar import GeoGuessrClient, Slot


async def main():
    async with GeoGuessrClient() as gg:
        avatar = await gg.get_avatar("656461a8a02239a1b6a4482e")
        print([item.id for item in avatar.items], avatar.win_animation)
        hair_glb = await gg.asset(avatar.item(Slot.HAIR).mesh_glb)  # one item's raw mesh
        static_png = await gg.full_body_png(avatar.user_id)  # GeoGuessr's own static image


asyncio.run(main())
```

## Command line

```sh
geoguessr-avatar render <user> [-a ANIMATION] [-t SECONDS | -p PROGRESS] [-o FILE]
                        [--framing fixed|fit] [--zoom 0.85] [--size 540x720] [--background '#1d1b2e']
geoguessr-avatar model <user> [-a ANIMATION] [-t SECONDS | -p PROGRESS] [-o FILE]   # 3D model
geoguessr-avatar info <user>       # equipped items and win animation
geoguessr-avatar animations        # list built-in animations
```

`<user>` is a user ID or a profile URL. Without `-o`, the file is named
`<user-id>_<animation>.png` (or `.glb`).

## Running on a server

Rendering runs on the CPU (software WebGL), so no GPU is needed. On Linux, install the
browser together with its system libraries:

```sh
playwright install --with-deps --only-shell chromium
```

Or use the included Dockerfile:

```sh
docker build -t geoguessr-avatar .
docker run --rm -v "$PWD:/out" geoguessr-avatar render <user> -o /out/win.png
```

## Troubleshooting

| Message | Fix |
|---|---|
| `Chromium for Playwright is not installed` | Run `playwright install chromium` (on Linux: `playwright install --with-deps --only-shell chromium`). |
| `no GeoGuessr user with ID ...` | Check the ID. It's the 24-character code at the end of the profile URL. |
| `unknown animation ...` | Check the spelling; the error suggests close matches. `geoguessr-avatar animations` lists them all. |
| Avatar cut off at the top or side | Use `zoom=0.85`, or `framing="fit"`. |
| First render is slow | The first render downloads the player's models and textures. They're cached after that. |

To see what's happening, turn on logging: `logging.basicConfig(level=logging.DEBUG)`.

## API reference

Everything is importable from `geoguessr_avatar`.

**Renderers**
- `SyncAvatarRenderer(cache_dir=None, software_gl=True)`: blocking. `.render(...)`, `.close()`, usable as `with`.
- `AvatarRenderer(client=None, cache_dir=None, software_gl=True)`: async. `await .render(...)`, `await .aclose()`, usable as `async with`.
- `render(user, animation=None, *, time, progress, width, height, framing, zoom, margin, background, supersample)` returns a `RenderResult`. `user` can also be an `Avatar` you already fetched.
- `export_model(user, animation=None, *, time, progress)` returns a `ModelResult`.
- `render_avatar(user, animation=None, **options)`: one-shot helper.
- `software_gl=False` uses the machine's GPU instead of software rendering.

**`RenderResult`**: `.png` (bytes), `.save(path)`, `.animation` (clip name or asset ID),
`.time` and `.duration` (seconds), `.bounds` (3D bounding box of the posed avatar).

**`ModelResult`**: `.glb` (bytes), `.save(path)`, `.animation`, `.time` (the pose) and
`.duration` (seconds).

**`GeoGuessrClient(ncfa=None, cache_dir=None)`** (async)
- `get_avatar(user)` returns an `Avatar`.
- `get_user(user)` returns the raw public profile as a dict.
- `get_assets([ids])` returns a list of `AvatarItem`.
- `get_background(user)` returns the equipped background, or `None`.
- `asset(path)`, `image(path)`, `full_body_png(user)` return bytes.

**Data**
- `Avatar`: `.user_id`, `.items`, `.item(Slot.X)`, `.win_animation`, `.emotes`.
- `AvatarItem`: `.id`, `.slot`, `.mesh_glb`, `.texture`, `.morph_target`, `.hides`, `.raw`.
- `Slot`: equipment slots (`HAIR`, `HATS`, `ANIMATION_WIN`, ...).
- `animations`: `BUILTIN_ANIMATIONS`, `WIN_ANIMATIONS`, `LOSE_ANIMATIONS`, `TAUNT_ANIMATIONS`, `IDLE_ANIMATIONS`.
- `parse_user_id(text)`: user ID from an ID or profile URL.

**Errors**: `UserNotFound` (subclass of `GeoGuessrError`), `BrowserNotInstalled`,
`ValueError` for bad input, and `TimeoutError` from `SyncAvatarRenderer`.

## How it works

GeoGuessr doesn't serve posed avatar images; the site draws avatars live with three.js.
This package does the same in a headless Chromium:

1. reads the player's equipped items from GeoGuessr's public avatar API,
2. downloads the 3D models, textures and animation clips (cached on disk),
3. assembles the avatar the way the site does: clothing on one skeleton, hats squashing
   hair, costumes hiding what's under them, face expressions, held items,
4. jumps to the chosen moment and renders it with a toon shader matching the site's look.

For a 3D model, step 4 instead swaps in plain materials and saves the posed scene and the clip
with three.js's glTF exporter.

| Data | Endpoint |
|---|---|
| Equipped items | `GET /api/v4/avatar/user/{userId}` |
| Asset lookup by ID | `GET /api/v4/avatar/assets?ids=...` |
| Models, textures, win-animation clips | `https://www.geoguessr.com/assets/{path}` |
| Built-in clips, head model | `/static/avatar-assets/animations/{NAME}.glb`, `/static/avatar-assets/head/head.glb` |
| Profile, static full-body image | `GET /api/v3/users/{userId}`, `/images/plain/{path}` |

**Caching:** files go to `~/.cache/geoguessr-avatar` (or `$XDG_CACHE_HOME/geoguessr-avatar`;
change it with `cache_dir=`). Models and textures are kept forever because their URLs
change whenever the content does. Built-in clips are re-checked weekly. A player's equipped
items are always fetched fresh.

## Limitations

- Renders are still images. For an animated image, render several frames and combine them
  yourself. 3D models do include the animation.
- Club-branded clothing shows its base texture, without the club logo.
- Pets, badges and emote bubbles are not drawn.
- The random idle eye-blink isn't reproduced.

## Development

```sh
uv sync
uv run playwright install chromium
uv run pytest                                      # offline tests
GEOGUESSR_AVATAR_NETWORK_TESTS=1 uv run pytest     # + live site and Chromium
uv run ruff check . && uv run ruff format --check .
uv run scripts/make_docs_images.py                 # regenerate the README images
```

CI runs the live tests weekly, so a failing scheduled run means geoguessr.com changed
something. `src/geoguessr_avatar/web/vendor/` holds three.js r185 (MIT, see
`three-LICENSE`), the same version geoguessr.com uses, plus its Draco decoder.

### Releasing

1. Bump `version` in `pyproject.toml` and commit.
2. Create a GitHub release with a tag like `v0.1.0`. The `Publish to PyPI` workflow builds
   the package and uploads it.

## License

MIT
