# Contributing to Pretty GitHub

Thanks for helping expand the collection. Contributions can improve an existing template or add a completely new GitHub profile style.

## Before contributing

- Submit only original work or assets you have permission to redistribute.
- Do not reproduce paid templates from screenshots or include copyrighted artwork without permission.
- Remove API keys, tokens, email secrets, analytics identifiers, and private data.
- Replace personal portrait files with a clearly marked example or document that users must supply their own.
- Keep changes focused; do not redesign unrelated templates in the same contribution.

## Required structure for a new design

```text
Design-Name/
├── .github/workflows/update-profile.yml  # when automatic data is used
├── assets/                               # generated and source assets
├── scripts/                              # generators and requirements
├── config.json                           # when the design is configurable
├── README.md                             # real rendered preview
└── SETUP.md                              # complete manual and AI setup
```

Static designs may omit files they do not need, but every design must include `README.md` and `SETUP.md`.

## Setup guide requirements

The guide must explain:

1. How to create the special GitHub profile repository.
2. Exactly which files and hidden folders to copy.
3. Every field, link, username, and personal asset the user must replace.
4. Dependencies and exact generation commands.
5. How to preview the README locally and on GitHub.
6. How to enable and troubleshoot the GitHub Action.
7. A copy-paste AI setup prompt tailored to the design.

## Design quality checklist

- The style is visually distinct from existing designs.
- Text remains readable at GitHub’s profile width.
- SVG files contain accessible `role` and `aria-label` attributes.
- Animations respect reduced-motion preferences where practical.
- Generated assets do not depend on a paid or fragile third-party card service.
- Long user values are clipped, wrapped, or documented clearly.
- The checked-in preview renders without running a server.

## Verification checklist

Before opening a pull request:

- Run every documented generator command.
- Parse or open every generated SVG and check it visually.
- Preview the design’s `README.md`.
- Verify all relative links and image paths.
- Confirm the workflow file is inside `.github/workflows/`.
- Confirm the workflow requests only the permissions it needs.
- Make sure no `.venv`, `__pycache__`, nested `.git`, or secret files are included.

## Pull requests

Describe what changed, include a preview image when useful, and list the commands you ran to verify the result. Keep one new design or one focused improvement per pull request.
