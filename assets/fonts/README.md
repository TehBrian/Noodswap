# Card Fonts

Bundled card fonts for text overlay rendering.

Styles are selected by font key in bot data, then mapped to explicit files in
`bot/fonts.py` (`FONT_FILE_MAP`). Keep runtime filenames in sync with that
mapping.

Required files by style:
- `classic`: `Arial.ttf`, `Arial Bold.ttf`
- `serif`: `Times New Roman.ttf`, `Times New Roman Bold.ttf`
- `mono`: `Courier New.ttf`, `Courier New Bold.ttf`
- `script`: `SnellRoundhand.ttc`, `SnellRoundhand Bold.ttc`
- `spooky`: `Papyrus.ttc`, `Papyrus Bold.ttc`
- `pixel`: `Menlo.ttc`, `Menlo Bold.ttc`
- `playful`: `Comic Sans MS.ttf`, `Comic Sans MS Bold.ttf`

`classic` is the default display font and is also eligible in random font rolls.
