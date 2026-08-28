# Account Provisioning at Scale — Capability Atlas Chapter

**Scope statement (explicit):** Everything below concerns *legitimate identity/infrastructure operations on systems the operator owns* — running your own IdP for your own org/tenants, standing up service accounts and test users in environments you control, and driving IAM automation (Terraform/Pulumi/Ansible) against your own cloud accounts or self-hosted stacks. Nothing here concerns provisioning identities on systems you don't own or control.

**Hardware envelope evaluated:** Mac Studio M5 Max (18-core CPU, 128GB unified memory, 8TB SSD, $2,499) and M5 Ultra (36-core CPU, up to 512GB unified memory — 256GB available at the Sept 22 2026 launch — 16TB SSD, $5,499).

---

## Bottom line

A single Mac Studio comfortably hosts **dozens to a few hundred** independent self-hosted IdP instances (Keycloak/Authentik/FreeIPA) by memory math alone, and its cores are fast enough that local Postgres-backed synthetic-user seeding is a non-issue. But the moment provisioning talks to a *real* external IAM API (AWS, Okta, Auth0, Azure AD), throughput is capped by that vendor's rate limit, not by anything the M5 Ultra brings — a $200/month cloud shell provisions AWS IAM identities exactly as fast as a $5,499 workstation. And Kubernetes single-node pod ceilings (110–250) cap multi-tenant container orchestration well below what the RAM alone would suggest, on either config.

---

## 1. What runs: self-hosted IdP memory math

All figures below are **app/pod-level footprints only** (Keycloak, Authelia) or **whole-stack minimums including their required DB/cache** (Authentik, FreeIPA), as sourced — this distinction matters and is called out per row. Usable RAM assumes ~20GB reserved for macOS + container-runtime VM + per-instance Postgres overhead (an estimate, not a cited figure — flagged in Confidence & gaps).

| IdP | Cited unit footprint | Source |
|---|---|---|
| Keycloak | 1,250 MB/pod base (caches + 10,000 sessions); +500 MB per additional 100,000 active sessions in a 3-node cluster, tested to 200,000 sessions | [Red Hat build of Keycloak 26.0 sizing guide](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/high_availability_guide/concepts-memory-and-cpu-sizing-) |
| Authelia | 20–25 MB RAM, <1% CPU idle / <5% under load | [Authelia GitHub discussion #6048](https://github.com/authelia/authelia/discussions/6048) |
| Authentik | 2GB+ **whole VPS stack** (app + Postgres + Redis) | [elest.io IdP comparison](https://blog.elest.io/authentik-vs-authelia-vs-keycloak-choosing-the-right-self-hosted-identity-provider-in-2026/) |
| FreeIPA | 2GB RAM (CA-full) / 1GB (CA-less or replica without CA) | [FreeIPA ARM page](https://www.freeipa.org/page/ARM) |

**Instance density at 128GB (M5 Max, ~108GB usable) vs 512GB full / 256GB launch-available (M5 Ultra, ~492GB / ~236GB usable):**

- **Keycloak, minimal sizing** (1.25GB/instance → 10,000 sessions each): 108/1.25 ≈ **86 instances** at 128GB → up to 860K cumulative sessions; 492/1.25 ≈ **393 instances** at full 512GB (236/1.25 ≈ **188** at 256GB launch availability).
- **Keycloak, large-tenant sizing** (1.25GB + 2×500MB = 2.25GB/instance → ~210K sessions each, near Red Hat's tested 200K ceiling): 108/2.25 ≈ **48 instances** at 128GB; 492/2.25 ≈ **218 instances** at full 512GB (236/2.25 ≈ **104** at launch). Cross-reference §2 — CPU, not memory, caps how much of that session capacity is actually usable simultaneously.
- **Authentik** (2GB whole-stack minimum): 108/2 ≈ **54 tenant stacks** at 128GB; 492/2 ≈ **246** at full 512GB (236/2 ≈ **118** at launch).
- **FreeIPA** (2GB CA-full / 1GB CA-less): **54 CA-full realms or 108 CA-less replicas** at 128GB; **246 / 492** at full 512GB (**118 / 236** at launch).
- **Authelia** (20–25MB): memory is irrelevant at this scale (108GB / 25MB ≈ 4.3M theoretical) — the real ceiling is container/process count, covered in §3.

**Apple Silicon build availability, closing the flagged gap:** Keycloak has shipped official multi-arch (amd64+arm64) Quarkus/WildFly images since v17.0.1/18, confirmed by a Keycloak maintainer ("we're now providing multi-arch for Quarkus and WildFly distributions") — [GitHub discussion #8846](https://github.com/keycloak/keycloak/discussions/8846). Authentik's `goauthentik/server` image is also built for both amd64 and arm64 via cross-compilation in its Dockerfile — [goauthentik/authentik Dockerfile](https://github.com/goauthentik/authentik/blob/main/lifecycle/container/Dockerfile). Authelia ships as a single Go binary that already runs on Raspberry Pi-class ARM64 — [selfhosting.sh comparison](https://selfhosting.sh/compare/authentik-vs-authelia/). Net: no ARM64-native gap remains for the three container-based options; FreeIPA's ARM64 story is thinner (see §6).

---

## 2. Provisioning throughput — API-rate-bound vs CPU-bound (headline distinction)

**Headline: for both Terraform and Pulumi, the apply-time bottleneck is the target cloud provider's API rate limit, not the tool's engine or the local machine's CPU** — explicitly stated for both tools: "cloud provider API rate limits, not tool engine performance" — [Pulumi vs Terraform 2026](https://tech-insider.org/pulumi-vs-terraform-2026/). The same holds for OpenTofu — [OpenTofu rate-limiting fix guide](https://oneuptime.com/blog/post/2026-03-20-fix-api-rate-limiting-opentofu/view).

- **Concrete external ceiling:** AWS STS caps credential-API calls at **600 requests/sec per account per region** — [same source](https://oneuptime.com/blog/post/2026-03-20-fix-api-rate-limiting-opentofu/view). Every 36 M5 Ultra cores in the world cannot move this number; it lives outside the box.
- **Default local parallelism:** Terraform defaults to 10 concurrent resource ops — [oneuptime parallelism guide](https://oneuptime.com/blog/post/2026-02-23-how-to-use-parallelism-flag-for-faster-applies/view). Pulumi defaults to *unlimited* concurrency (tunable via `--parallel`) — [Pulumi vs Terraform 2026](https://tech-insider.org/pulumi-vs-terraform-2026/), and a benchmark recorded a 3.17x (300%) speedup over Terraform on parallel SNS/SQS creation — [Pulumi Python performance benchmark](https://www.pulumi.com/blog/benchmarking-python-performance/) — but that same benchmark caveats "performance parity at scale when API-limited." **Reading these together: Pulumi's concurrency advantage only shows up below the target API's rate ceiling; once you hit AWS STS's 600 req/s (or any other vendor limit), tool choice stops mattering and both tools throttle identically.**
- **Ansible** (SSH-fanout provisioning, e.g. local user/service-account creation across a fleet): 5 forks by default; guidance recommends 50–100 forks for lightweight read-only tasks, 15–30 for I/O-heavy ones — [Ansible forks guide](https://cyberpanel.net/blog/ansible-forks-guide-2026), [ansiblebyexample forks article](https://www.ansiblebyexample.com/articles/ansible-forks-parallel-execution-and-performance). This path is CPU/I-O bound on the control node and *does* benefit from the M5's core count, since there's no external API in the loop.

**Where the Mac's CPU actually becomes the bottleneck:** only when provisioning against a *self-hosted* IdP on the same box (no external rate limiter). Keycloak's own CPU-scaling guidance: **1 vCPU per 15 password-based logins/sec** (tested to 300/sec, ≈20 vCPUs) and **1 vCPU per 120 client-credential grants/sec** (tested to 2,000/sec, ≈16.7 vCPUs) — [Red Hat sizing guide](https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/high_availability_guide/concepts-memory-and-cpu-sizing-). A 36-core M5 Ultra has nominal headroom over both tested ceilings (~1.8x and ~2.2x respectively) *if* Apple Silicon cores map 1:1 onto Red Hat's "vCPU" sizing unit — an unverified assumption (see §6). Red Hat's own testing stops at those numbers, so anything beyond is extrapolation regardless of core count.

**DB seeding rates for synthetic users:**
- Optimized Postgres bulk insert (COPY + transaction tuning): **394,477 rows/sec** — [PostgreSQL insertion speed writeup](https://balkrishan-nagpal.medium.com/postgres-how-i-improved-data-insertion-speed-by-a-factor-of-more-than-1000x-1a968e736e86). At this rate, 1M synthetic user rows ≈ **2.5 seconds**.
- Typical/conservative bulk load: "tens of thousands of rows/sec" for narrow tables — [Cybertec bulk-loading guide](https://www.cybertec-postgresql.com/en/bulk-loading-huge-amounts-of-data/). At, say, 20K rows/sec, 1M rows ≈ **50 seconds**.
- Purpose-built synthetic-data tools (e.g. GenRocket) claim millions-to-billions of rows in minutes with multi-threaded partition engines — [GenRocket](https://www.genrocket.com/synthetic-data-generation/) (vendor-sourced, medium confidence).
- **Caveat, flagged as a gap:** these are raw Postgres INSERT rates, not IdP admin-API ingestion rates. Actually creating those million users *inside* Keycloak/Authentik (via their own REST/SCIM APIs, with password hashing per record) will be materially slower than the raw DB numbers above — no source found quantifying that gap.

---

## 3. Multi-tenant dev/test density

**Containers:** 100–200+ containers "easily," theoretical max 400–500+ for simple workloads on a 128GB machine, with a typical container using 50–500MB — [container density comparison](https://oneuptime.com/blog/post/2026-01-16-containers-vs-vms-density-efficiency-comparison/view). Scaling that ratio to 512GB gives a rough envelope of ~400–800 comfortable / theoretical 1,600–2,000+ for simple workloads — **this 512GB figure is my extrapolation from the 128GB fact, not independently sourced.**

**Podman on Apple Silicon — a correction to the sourced claim.** The fact base states Podman "leverages native ARM64 containerization without VM overhead" on M1/M2 — [rahasak Podman/Docker switch article](https://medium.com/rahasak/switching-from-docker-desktop-to-podman-on-macos-m1-m2-arm64-cpu-7752c02453ec). Supplemental research shows this overstates it: macOS's XNU kernel lacks the Linux namespace/cgroup primitives containers require, so **Podman Machine on macOS still runs containers inside a lightweight Linux VM** via Apple's Virtualization Framework / libkrun — [Red Hat: How Podman runs on Macs](https://www.redhat.com/en/blog/podman-mac-machine-architecture), [oneuptime Podman Apple Silicon guide](https://oneuptime.com/blog/post/2026-03-16-podman-machine-apple-silicon/view). What Podman actually avoids on Apple Silicon is *architecture emulation* (arm64 containers on an arm64 VM, no Rosetta-style translation) — not virtualization itself. This matters for the density numbers above: it's unclear whether the cited 100–500 container figure was measured on bare-metal Linux (no VM layer at all) or inside a macOS-style VM; the two aren't guaranteed comparable (flagged in §6).

Separately: Docker currently outperforms Podman on Apple Silicon for certain workloads, with a Rosetta translation layer available for x86 images — [Docker Apple Silicon performance setup](https://medium.com/@guillem.riera/the-most-performant-docker-setup-on-macos-apple-silicon-m1-m2-m3-for-x64-amd64-compatibility-da5100e2557d).

**Single-node Kubernetes ceiling — the headline constraint, independent of RAM:** 110 pods/node is the recommended standard; up to 250 pods/node on major managed services with proper configuration — [plural.sh pods-per-node guide](https://www.plural.sh/blog/how-many-pods-per-node/). On a 128GB single node, practical pod density is **gated by this 110–250 ceiling, not memory**, for reasonably-sized workloads — same source — and a node's CIDR block can cap it at 256 pods max regardless of hardware. **This ceiling is a flat number that does not move between the 128GB and 512GB configs** — buying the bigger Mac Studio does not buy more pods per node; it only lets each pod be bigger.

---

## 4. Hard ceilings and nearest server-class equivalent

| Ceiling | Value | Moves with more RAM/cores? |
|---|---|---|
| AWS STS credential API | 600 req/sec/account/region | No — external, vendor-side |
| Keycloak validated login throughput | 300 password logins/sec tested max | Only up to ~20 vCPU-equivalent; unvalidated beyond |
| Keycloak validated client-credential throughput | 2,000 grants/sec tested max | Only up to ~16.7 vCPU-equivalent; unvalidated beyond |
| Keycloak session-scaling test ceiling | 200,000 sessions tested | Extrapolation beyond this is unverified |
| Kubernetes pods/node | 110 standard, 250 with tuning, 256 CIDR-hard-cap | No — flat per-node ceiling |

**Nearest server-class RAM equivalent:** the closest AWS memory-optimized matches to the M5 Ultra's 512GB are the **r7i.12xlarge (48 vCPU / 384GB)** and **r8i-flex.16xlarge (64 vCPU / 512GB)** — [AWS memory-optimized instance specs](https://docs.aws.amazon.com/ec2/latest/instancetypes/mo.html). This is a **RAM/vCPU-count spec match only, not a performance-equivalence claim** — cloud memory-optimized instances run at an 8:1 GB-per-vCPU ratio, while the M5 Ultra runs at roughly 14:1 (512GB / 36 cores). Since Red Hat's Keycloak CPU-throughput formulas are calibrated on x86 "vCPU" units, and no source establishes how Apple Silicon P/E cores map onto that unit, translating the M5 Ultra's 36 cores into a specific logins/sec number is not something this evidence base supports — treat any such number as a rough upper bound, not a validated figure.

---

## 5. Where "enterprise-in-a-box" holds vs breaks

**Holds:**
- Self-hosted IdP fleet density: 50–250+ independent Keycloak/Authentik/FreeIPA tenant instances fit comfortably in unified memory (§1) — genuinely comparable to what would otherwise need a small dedicated cluster.
- Local, non-cloud provisioning workflows (Postgres synthetic-user seeding, Ansible-driven local fan-out, IaC applied against a self-hosted backend) are CPU/disk-bound and the M5's core count plus fast NVMe removes any local-hardware ceiling for realistic dev/test volumes.
- IaC tool engine overhead (Terraform/Pulumi/Ansible themselves) is never the bottleneck on this hardware, at any tier.

**Breaks:**
- Any provisioning path against a real external IdP/cloud IAM API (AWS IAM/STS, Okta, Auth0, Azure AD) is capped by that vendor's rate limit (e.g. 600 req/s for AWS STS) — the M5 Ultra's cores and memory are irrelevant here; a modest cloud VM provisions identities against AWS exactly as fast.
- Single-node Kubernetes multi-tenancy caps at 110–250 pods/node **regardless of which Mac Studio config you buy** — the 512GB unit does not buy more tenants-as-pods, only bigger pods, so the "enterprise" k8s multi-tenant story tops out at small/mid scale on one node.
- Keycloak's own vendor sizing guidance stops validating at 300 logins/sec, 2,000 client-credential grants/sec, and 200,000 sessions — claiming the M5 Ultra's extra cores buy proportionally more throughput past those points is not supported by any source here.
- The "no VM overhead" framing for Apple Silicon containers does not hold up under closer sourcing (§3) — meaning container-density figures sourced from generic/Linux-host benchmarks may not transfer 1:1 to a macOS host running the same workload inside Apple's virtualization layer.

---

## 6. Confidence & gaps

**High confidence** (official vendor docs or maintainer-confirmed, cross-checked): Keycloak memory/CPU sizing formulas (Red Hat), IaC API-rate-limit bottleneck (multiple independent sources agreeing), Kubernetes pods-per-node ceilings, Keycloak/Authentik ARM64 multi-arch image availability (maintainer statement + Dockerfile inspection).

**Medium confidence** (single blog/vendor source, or benchmark methodology not fully disclosed): Authentik and FreeIPA memory minimums (single comparison-site sources), Docker container density figures (one blog post, host OS/hardware for the benchmark not stated), GenRocket synthetic-data throughput (vendor marketing copy), Pulumi's 3.17x benchmark (single test case, not necessarily representative of identity-provisioning-shaped workloads).

**Open questions / gaps not closed by this pass:**
1. No data maps Apple Silicon performance/efficiency cores onto Red Hat's Keycloak "vCPU" sizing unit — the 36-core M5 Ultra's actual login/sec ceiling cannot be stated with confidence, only bounded loosely against the x86-tested figures.
2. The Docker/Podman container-density fact (100–500+ containers) doesn't specify its host OS/hardware; combined with the Podman-on-macOS VM correction in §3, it's unclear whether that density figure transfers to a macOS host at all.
3. FreeIPA's "10+ minute ARM startup" caveat is sourced from SD-card-based ARM SBCs (e.g. Raspberry Pi-class), not Apple Silicon Macs with NVMe SSDs — whether that penalty applies to a Mac Studio is untested in any source found.
4. No benchmark exists (in this evidence base) for IdP *admin-API* user-creation throughput specifically — all DB-seeding figures are raw Postgres INSERT rates, which likely overstate real end-to-end account-creation speed once password hashing and IdP business logic are in the loop.
5. No source in this pass benchmarks any of these IdPs actually running on M5 Max/Ultra silicon specifically — every figure here is generic or x86-cloud-sourced and applied to the stated hardware envelope by inference, not measured on it.
6. The 512GB M5 Ultra's "256GB available at Sept 22 2026 launch" constraint (given in the task's hardware envelope) is treated as-given; no source here explains or corroborates it, and it materially changes the density tables in §1 (roughly halving every large-config figure).

---

### result (6-line chapter summary)
1. Self-hosted IdPs (Keycloak/Authentik/FreeIPA) fit 50–250+ independent tenant instances in unified memory at 128GB–512GB, per direct memory-math from official/vendor sizing docs.
2. IaC apply throughput (Terraform/Pulumi/OpenTofu) is bottlenecked by target-cloud API rate limits (e.g. AWS STS: 600 req/s), not local CPU — this is the single most important framing for the whole domain.
3. Local Postgres-backed synthetic-user seeding is fast (up to ~394K rows/sec optimized) and CPU/disk-bound, so the M5's cores and NVMe genuinely help there.
4. Single-node Kubernetes multi-tenancy is capped at 110–250 pods/node regardless of RAM tier — the 512GB config buys bigger pods, not more tenants.
5. Keycloak's own vendor-validated ceilings (300 logins/sec, 2,000 client-credential grants/sec, 200K sessions) bound what's provable on this hardware; going further is unverified extrapolation.
6. "Enterprise-in-a-box" holds for local self-hosted-IdP density and dev/test provisioning speed, but breaks wherever a real external IAM API or single-node k8s pod ceiling is in the loop — both are hardware-independent limits.

### evidence
- Keycloak memory/CPU sizing: https://docs.redhat.com/en/documentation/red_hat_build_of_keycloak/26.0/html/high_availability_guide/concepts-memory-and-cpu-sizing-
- IaC API-rate-limit bottleneck: https://tech-insider.org/pulumi-vs-terraform-2026/ and https://oneuptime.com/blog/post/2026-03-20-fix-api-rate-limiting-opentofu/view
- Kubernetes pods/node ceiling: https://www.plural.sh/blog/how-many-pods-per-node/
- Keycloak ARM64 multi-arch confirmation: https://github.com/keycloak/keycloak/discussions/8846
- Podman-on-macOS VM correction: https://www.redhat.com/en/blog/podman-mac-machine-architecture

### confidence
High for vendor-documented sizing/throughput figures and the API-rate-bound framing (multiple independent corroborating sources); medium for single-source density/vendor-marketing figures; low/unverified for anything requiring Apple Silicon-specific core-to-vCPU translation, since no source measures these IdPs running natively on M-series silicon.

### open_questions
1. Apple Silicon core-to-Keycloak-"vCPU" mapping is undocumented — actual login/sec ceiling on M5 Ultra is unbounded by evidence, only loosely inferred.
2. Container-density figures' host OS/hardware is unstated, and Podman-on-macOS's VM layer (corrected in §3) may invalidate direct transfer of those numbers to a Mac Studio.
3. FreeIPA's ARM slow-startup note is from SD-card SBCs, not tested on Apple Silicon NVMe.
4. No IdP admin-API (as opposed to raw DB) user-creation throughput benchmark exists in the evidence base.
5. No source benchmarks any evaluated IdP running natively on M5 Max/Ultra hardware.
