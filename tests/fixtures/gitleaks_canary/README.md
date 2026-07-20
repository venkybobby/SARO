# Gitleaks canary fixture (STORY-363)

`seeded_secret.txt` contains a **fake** AWS-access-key-shaped string. It exists
so CI can prove the secret-scanning gate works: the `secret-scan` job runs
gitleaks against this directory with the DEFAULT ruleset (not the repo config)
and asserts the scan FAILS. The repo-wide scan allowlists this path in
`.gitleaks.toml`, so the canary never blocks a build by itself.

Never put a real credential here — or anywhere else in the repo.
