name: Cyberpunk Status Panel

on:
  schedule:
    # refresh every 6 hours
    - cron: "0 */6 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  status:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install requests

      - name: Generate status-panel.svg
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          USERNAME: ${{ github.repository_owner }}
        run: python scripts/generate_status.py

      - name: Commit & push
        run: |
          git config user.name github-actions
          git config user.email github-actions@github.com
          git add status-panel.svg
          if git commit -m "chore: refresh system status panel"; then
            git push
          fi
