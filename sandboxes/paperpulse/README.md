# Run PaperPulse in OpenShell — end to end

One OpenShell sandbox image that runs **all of MARS-PaperPulse** (FastAPI backend +
Next.js UI), the same way NVIDIA's `gemini` sandbox packages the Gemini CLI.

```
sandboxes/paperpulse/
├── Dockerfile            # the single image (backend + frontend)
├── policy.yaml           # egress + filesystem + user policy for the sandbox
├── start-paperpulse.sh   # launches both services inside the sandbox
└── README.md             # this file
```

---

## 1. What OpenShell is (in 30 seconds)

OpenShell is NVIDIA's **security sandbox for AI agents**. It runs your container but
wraps it in:

- **Filesystem lockdown** — your code at `/app` is read-only; only `/sandbox` and
  `/tmp` are writable.
- **Network lockdown** — the sandbox can reach *only* the hosts listed in
  `policy.yaml`. Everything else is denied by default. This is the whole point: the
  research agent runs LLM-generated code, and the firewall guarantees it can only
  talk to the LLM endpoints you approved.

Pieces involved:
- **gateway** — a local control-plane daemon (embedded k3s in Docker) that creates
  and supervises sandboxes. Must be running and healthy before anything works.
- **sandbox** — one running container built from this image, governed by `policy.yaml`.
- **forward** — publishes a sandbox port to the host so your browser can reach the UI.

---

## 2. One-time host setup

Do these **once** on the machine that runs the sandbox (we hit all three during
bring-up — they are the usual snags):

**a) Docker usable without sudo** (the gateway drives Docker as your user):
```bash
sudo usermod -aG docker $USER
# log out/in (or reboot) so it applies to your systemd user session
docker ps         # must work WITHOUT sudo
```

**b) Exactly one OpenShell gateway.** If you have both the snap and the `.deb`, they
fight over port 17670. Keep one. We disabled the snap and used the `.deb`:
```bash
sudo snap stop --disable openshell.gateway     # if a snap install exists
openshell status                                # must show  Status: Connected
```

**c) Let the sandbox reach the gateway through UFW.** If `ufw` is active it blocks
the sandbox→gateway connection (the sandbox will crash-loop with "Policy fetch
failed"). Allow the OpenShell bridge to the gateway port:
```bash
# bridge name: docker network inspect openshell-docker -f '{{index .Options "com.docker.network.bridge.name"}}'
sudo ufw allow in on br-9624fee50448 to any port 17670 proto tcp comment 'openshell sandbox->gateway'
```

Verify the gateway is healthy before continuing:
```bash
openshell status        # Status: Connected
```

---

## 3. Build the image

From the **repo root** (`MARS-PaperPulse/`), because the build needs both
`backend/` and `frontend/`:

```bash
docker build -t openshell-paperpulse:latest -f sandboxes/paperpulse/Dockerfile .
```

First build is slow (Python scientific stack + Next.js build). Rebuilds are cached.

---

## 4. Start it (with your Azure key)

Your Azure creds live in `backend/.env`. This command reads them from there (so the
key is never typed on the command line), applies the egress policy, forwards the UI
on host port **3100**, and launches both services:

```bash
cd MARS-PaperPulse
getval(){ grep -E "^$1=" backend/.env | tail -1 | sed -E "s/^$1=//; s/^\"//; s/\".*$//"; }

openshell sandbox create --from openshell-paperpulse:latest --name paperpulse \
  --policy sandboxes/paperpulse/policy.yaml \
  --forward 3100 \
  --env FRONTEND_PORT=3100 --env PORT=8000 --env CMBAGENT_LLM_PROVIDER=azure \
  --env AZURE_OPENAI_API_KEY="$(getval AZURE_OPENAI_API_KEY)" \
  --env AZURE_OPENAI_ENDPOINT="$(getval AZURE_OPENAI_ENDPOINT)" \
  --env AZURE_OPENAI_DEPLOYMENT="$(getval AZURE_OPENAI_DEPLOYMENT)" \
  --env AZURE_OPENAI_API_VERSION="$(getval AZURE_OPENAI_API_VERSION)" \
  --no-auto-providers --no-tty -- start-paperpulse
```

This command **stays in the foreground**, streaming both services' logs and holding
the port-forward. Leave it running. You'll see:

```
✓ Forwarding port 3100 to sandbox paperpulse in the background
  Access at: http://127.0.0.1:3100/
[paperpulse] backend  -> http://0.0.0.0:8000  (docs at /docs)
[paperpulse] frontend -> http://0.0.0.0:3100
✓ Ready in ...   (Next.js)
Registered LLM provider: azure
```

> To run it detached instead, prefix with `nohup ... &` or run it inside `tmux`.

**Notes**
- Uses the Azure host `azureft.openai.azure.com` (already in `policy.yaml`). If your
  Azure resource differs, edit that host in `policy.yaml` — no image rebuild needed,
  `--policy` is read at create time; just recreate the sandbox.
- The real Python interpreter is `/usr/bin/python3.12` (the venv symlinks to it), so
  the policy binds egress to that path. Keep that in mind if you add providers.

---

## 5. Open it in the browser (VS Code remote forwarding)

The forward binds `127.0.0.1:3100` on the server. In VS Code Remote, the **Ports**
panel auto-detects it (or add it manually) and tunnels it to your laptop.

Open **http://localhost:3100** on your laptop.

Why one port is enough: the frontend calls the backend through Next.js's built-in
proxy (relative `/api/*` and same-origin `/ws/*`), which forwards to `localhost:8000`
*inside* the sandbox. So the browser only ever needs `:3100`.

---

## 6. Use it — create a task and run stages

### From the UI
1. Open http://localhost:3100.
2. (Optional) click the **gear / Settings** icon to confirm the **Azure** provider
   shows **configured**.
3. On the deep-research wizard, type a research pitch (e.g. *"gradient boosting to
   predict bike-share demand from weather and calendar features"*), optionally
   upload data, and create the task.
4. **Stage 1 — Idea Generation**: click **Run/Execute**. The console panel streams
   the multi-agent output live over WebSocket. When it finishes, the generated
   research idea appears; review/edit it.
5. **Stage 2 — Method Development**: click **Run** on Stage 2 (unlocked once Stage 1
   is complete). It builds the methodology from the Stage 1 idea; the console streams
   again and the result renders when done.
6. Stages 3 (Experiment) and 4 (Paper) work the same way, each building on the last.

### From the API (what the UI calls under the hood)
```bash
B=http://127.0.0.1:3100/api/deepresearch
# create
TID=$(curl -s -X POST $B/create -H 'Content-Type: application/json' \
  -d '{"task":"...your pitch...","data_description":""}' | grep -oE '"task_id":"[^"]+"' | cut -d'"' -f4)
# run stage 1, then poll until status=completed
curl -s -X POST $B/$TID/stages/1/execute -d '{}'
curl -s $B/$TID/stages/1/content        # repeat until "status":"completed"
# run stage 2 (requires stage 1 complete)
curl -s -X POST $B/$TID/stages/2/execute -d '{}'
curl -s $B/$TID/stages/2/content
```
Stage execution is asynchronous — `execute` returns `{"status":"executing"}` and the
work runs in the background; poll `.../content` (or watch the console endpoint) until
`status` is `completed` or `failed`.

---

## 7. Stop / start / from scratch

The sandbox lifecycle is **create → delete** (there is no pause). State
(SQLite DB, task outputs) lives in `/sandbox/cmbdir` *inside the container* and is
lost on delete — see the persistence note below.

**Stop (keep the image):**
```bash
# Ctrl+C the foreground `sandbox create` command, then:
openshell forward stop 3100 paperpulse     # stop the port forward (if still up)
openshell sandbox delete paperpulse         # remove the sandbox container
```

**Start again:** re-run the `openshell sandbox create ...` command from Section 4.

**From scratch (clean slate):**
```bash
openshell sandbox delete paperpulse 2>/dev/null || true
docker build -t openshell-paperpulse:latest -f sandboxes/paperpulse/Dockerfile .   # only if code/policy changed
# then Section 4 again
```

**Check what's running:**
```bash
openshell sandbox list          # PHASE should be Ready
openshell status                # gateway Connected
```

> **Persistence (optional):** to keep tasks between restarts, mount a host dir onto
> `/sandbox/cmbdir` when creating the sandbox (driver-specific — see
> `openshell sandbox create --help` `--driver-config-json`), or export finished
> outputs with `openshell sandbox download paperpulse ...` before deleting.

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `start-paperpulse: command not found` on the host | It lives *inside* the image. Don't run it on the host — the `-- start-paperpulse` in `create` runs it in the sandbox. |
| Sandbox `ContainerRestarting` / "Policy fetch failed" | Sandbox can't reach the gateway — apply the UFW rule (Section 2c). |
| `openshell status` → corrupt message / connect error | Two gateways fighting for port 17670 — keep only one (Section 2b). |
| Stage fails instantly; container log shows `DENIED ... -> somehost:443` | That host isn't in `policy.yaml`. Add it (bound to `/usr/bin/python3.12`) and recreate the sandbox. |
| UI loads but API calls fail | Confirm the forward is up (`Access at: http://127.0.0.1:3100/`) and you opened `:3100`. |

Inspect the running sandbox:
```bash
C=$(docker ps --format '{{.Names}}' | grep '^openshell-paperpulse-' | head -1)
docker logs --tail 50 "$C"                       # egress DENIED lines, startup
docker exec "$C" tail -n 40 /sandbox/cmbdir/logs/backend.log
```

---

## 9. Other providers

`policy.yaml` ships with OpenAI, Anthropic, Gemini, Mistral, Azure and the tiktoken
asset host enabled, and PyPI open for runtime installs. **Azure and AWS Bedrock hosts
are account/region-specific** — Azure is set to `azureft.openai.azure.com`; for
Bedrock, uncomment the block and set `bedrock-runtime.<region>.amazonaws.com`. After
editing `policy.yaml`, just recreate the sandbox (no rebuild).
