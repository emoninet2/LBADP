# Card dimensions

Edit the `canvas` object in `card_config.json`, then run `python main.py`.

| preset | width x height |
| --- | --- |
| square | 1080 x 1080 |
| portrait (default) | 1080 x 1350 |
| story | 1080 x 1920 |
| landscape | 1920 x 1080 |
| wide | 1200 x 630 |

Example:

```json
"canvas": { "preset": "square" }
```

Custom dimensions:

```json
"canvas": { "preset": "custom", "width": 1400, "height": 1000 }
```

Named presets determine the output size. For custom dimensions, set preset to custom (or omit preset) and supply both width and height. Avoid mixing a named preset with width and height; the named preset wins. Each must be 600–4096 pixels, with an aspect ratio between 1:2 and 2:1. Existing field, section, color, and chart settings still apply.

Portrait/story use one column; square/landscape use two columns. Jump details span the top. Text wraps and spacing/type adapt to the available area. Output dimensions are exact. Selected content is never silently omitted or cropped; if too much content remains to fit, generation stops with guidance and retains the previous image. Choose a taller preset, shorten notes, or disable optional fields.

## Social media export presets

Set `canvas` to `{ "preset": "instagram_feed" }`, then run `python main.py`. Existing content toggles and custom dimensions still work. These are export formats for image posts, not a claim that each platform requires one universal size.

| Preset | Pixels |
| --- | --- |
| instagram_feed | 1080 x 1350 |
| instagram_square | 1080 x 1080 |
| instagram_story | 1080 x 1920 |
| facebook_feed | 1440 x 1800 |
| facebook_square | 1080 x 1080 |
| facebook_story | 1080 x 1920 |
| x_post | 1600 x 900 |
| x_square | 1080 x 1080 |
| linkedin_feed | 1200 x 628 |
| linkedin_square | 1200 x 1200 |

Story exports set canvas dimensions only; posting-app overlays may cover content near the edges.

References checked September 2026: LinkedIn single-image specifications https://www.linkedin.com/help/linkedin/answer/a427596/ ; Meta image placement specifications https://www.facebook.com/business/ads-guide/image/facebook-feed ; Instagram photo resolution https://help.instagram.com/1631821640426723 . Ad placement specifications are reference formats, not mandatory organic-post sizes.
