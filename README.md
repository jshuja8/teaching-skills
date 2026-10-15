# Teaching skills for Claude

Claude skills for university teaching work: checking course materials,
building assessments, and preparing content for Canvas. Each folder is a
self-contained skill with its own README, scripts and tests.

| Skill | What it does |
|---|---|
| [canvas-accessibility](canvas-accessibility/) | Audits and fixes accessibility issues in Word and PowerPoint files, and audits PDFs, before posting to Canvas |
| [canvas-rubric-builder](canvas-rubric-builder/) | Builds an analytic rubric from an assignment sheet and exports a CSV for Canvas's Import Rubric tool |

More skills will be added as they are cleaned up for release.

## Installing a skill

- **Claude apps:** zip the skill's folder and upload it as a custom skill in Claude's settings.
- **Claude Code:** copy the folder into `~/.claude/skills/`.

## Notes

- No student data or real course content is included. Examples and tests use synthetic files.
- Skills are provided as-is; review Claude's output before posting materials to students.

## License

MIT. See [LICENSE](LICENSE).
