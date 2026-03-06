# Diff Details

Date : 2026-03-06 10:13:30

Directory /Users/brian/stuff/dev/mine/discord-bots/Noodswap

Total : 48 files,  9829 codes, 296 comments, 1214 blanks, all 11339 lines

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details

## Files
| filename | language | code | comment | blank | total |
| :--- | :--- | ---: | ---: | ---: | ---: |
| [.dockerignore](/.dockerignore) | Ignore | 9 | 0 | 1 | 10 |
| [.github/workflows/cd.yml](/.github/workflows/cd.yml) | YAML | 44 | 0 | 9 | 53 |
| [.github/workflows/ci.yml](/.github/workflows/ci.yml) | YAML | 25 | 0 | 9 | 34 |
| [Dockerfile](/Dockerfile) | Docker | 15 | 0 | 9 | 24 |
| [Jenkinsfile](/Jenkinsfile) | Groovy | 40 | 0 | 7 | 47 |
| [README.md](/README.md) | Markdown | 71 | 0 | 22 | 93 |
| [assets/card\_fonts/README.md](/assets/card_fonts/README.md) | Markdown | 12 | 0 | 3 | 15 |
| [assets/card\_images/manifest.json](/assets/card_images/manifest.json) | JSON | 830 | 0 | 0 | 830 |
| [assets/frame\_overlays/README.md](/assets/frame_overlays/README.md) | Markdown | 8 | 0 | 3 | 11 |
| [card\_image\_distinct\_report.json](/card_image_distinct_report.json) | JSON | 10 | 0 | 0 | 10 |
| [deploy/docker-compose.prod.yml](/deploy/docker-compose.prod.yml) | YAML | 10 | 0 | 1 | 11 |
| [deploy/update.sh](/deploy/update.sh) | Shell Script | 16 | 2 | 7 | 25 |
| [docs/README.md](/docs/README.md) | Markdown | 1 | 0 | 0 | 1 |
| [docs/commands-and-ux.md](/docs/commands-and-ux.md) | Markdown | 107 | 0 | 20 | 127 |
| [docs/data-model.md](/docs/data-model.md) | Markdown | 48 | 0 | 8 | 56 |
| [docs/deploy-jenkins.md](/docs/deploy-jenkins.md) | Markdown | 50 | 0 | 18 | 68 |
| [docs/development-runbook.md](/docs/development-runbook.md) | Markdown | 25 | 0 | 6 | 31 |
| [docs/roadmap-and-known-issues.md](/docs/roadmap-and-known-issues.md) | Markdown | 22 | 0 | 0 | 22 |
| [noodswap/app.py](/noodswap/app.py) | Python | 10 | 2 | 4 | 16 |
| [noodswap/cards.py](/noodswap/cards.py) | Python | -400 | 0 | 15 | -385 |
| [noodswap/commands.py](/noodswap/commands.py) | Python | 596 | 2 | 71 | 669 |
| [noodswap/data/base\_values.json](/noodswap/data/base_values.json) | JSON | 241 | 0 | 1 | 242 |
| [noodswap/data/cards.json](/noodswap/data/cards.json) | JSON | 1,436 | 0 | 1 | 1,437 |
| [noodswap/fonts.py](/noodswap/fonts.py) | Python | 45 | 2 | 15 | 62 |
| [noodswap/frames.py](/noodswap/frames.py) | Python | 46 | 1 | 18 | 65 |
| [noodswap/images.py](/noodswap/images.py) | Python | 826 | 12 | 132 | 970 |
| [noodswap/migrations.py](/noodswap/migrations.py) | Python | 46 | 106 | 4 | 156 |
| [noodswap/morphs.py](/noodswap/morphs.py) | Python | 47 | 0 | 11 | 58 |
| [noodswap/presentation.py](/noodswap/presentation.py) | Python | 27 | 18 | 2 | 47 |
| [noodswap/rarities.py](/noodswap/rarities.py) | Python | 42 | 10 | 11 | 63 |
| [noodswap/repositories.py](/noodswap/repositories.py) | Python | 218 | 134 | 34 | 386 |
| [noodswap/services.py](/noodswap/services.py) | Python | 648 | 0 | 67 | 715 |
| [noodswap/settings.py](/noodswap/settings.py) | Python | 9 | 2 | 2 | 13 |
| [noodswap/storage.py](/noodswap/storage.py) | Python | 297 | 0 | 81 | 378 |
| [noodswap/views.py](/noodswap/views.py) | Python | 1,503 | 0 | 18 | 1,521 |
| [scripts/cache\_card\_images\_from\_backup.py](/scripts/cache_card_images_from_backup.py) | Python | 278 | 0 | 57 | 335 |
| [scripts/ensure\_distinct\_card\_images.py](/scripts/ensure_distinct_card_images.py) | Python | 240 | 0 | 54 | 294 |
| [scripts/export\_card\_image\_url\_backup.py](/scripts/export_card_image_url_backup.py) | Python | 35 | 0 | 13 | 48 |
| [scripts/generation\_economy\_report.py](/scripts/generation_economy_report.py) | Python | 191 | 0 | 38 | 229 |
| [scripts/migration\_smoke.py](/scripts/migration_smoke.py) | Python | 24 | 1 | 3 | 28 |
| [scripts/rarity\_odds.py](/scripts/rarity_odds.py) | Python | 122 | 0 | 16 | 138 |
| [scripts/rebalance\_base\_values.py](/scripts/rebalance_base_values.py) | Python | 123 | 2 | 29 | 154 |
| [tests/test\_app.py](/tests/test_app.py) | Python | 21 | 0 | 14 | 35 |
| [tests/test\_cards.py](/tests/test_cards.py) | Python | 2 | 0 | 1 | 3 |
| [tests/test\_commands.py](/tests/test_commands.py) | Python | 675 | 2 | 161 | 838 |
| [tests/test\_services.py](/tests/test_services.py) | Python | 183 | 0 | 39 | 222 |
| [tests/test\_storage.py](/tests/test_storage.py) | Python | 287 | 0 | 69 | 356 |
| [tests/test\_views.py](/tests/test_views.py) | Python | 668 | 0 | 110 | 778 |

[Summary](results.md) / [Details](details.md) / [Diff Summary](diff.md) / Diff Details