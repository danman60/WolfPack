---
name: Always deploy to droplet after push
description: After pushing WolfPack changes, always pull and restart on the DigitalOcean droplet
type: feedback
---

After every `git push` on WolfPack, immediately deploy to the droplet:

```bash
ssh droplet "cd /root/WolfPack && git stash --include-untracked && git pull && systemctl restart wolfpack-intel"
```

**Why:** The intel service runs on the droplet (159.89.115.95), not locally. Pushing without deploying means changes don't take effect and the user has to ask separately.

**How to apply:** Treat push + droplet deploy as a single atomic operation. Never push without deploying. Verify service is `active (running)` after restart.
