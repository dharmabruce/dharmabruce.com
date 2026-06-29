# dharmabruce

WordPress site <https://dharmabruce.com> — a relatively-anonymous personal blog
(speculative writing, Salience Engine notes, projects) under the long-standing
`dharmabruce` pseudonym. Its historical content is the old Blogger blog
`dharmabruce.blogspot.com` (2006–2024), imported into an **Attic** section.

DNS for `dharmabruce.com` is at GoDaddy (WHOIS-private); the cluster is k8s-sno.
The professional, real-name blog `blog.seanvaughan.com` stays on Blogger and is
intentionally **not** linked to this site (no redirect, no shared cert).

## Components

| Component | Image | Storage |
|---|---|---|
| `wordpress` | `wordpress:7.0-php8.3-apache` (official) | `wordpress-html` PVC (10Gi) — full docroot incl. imported media |
| `mariadb` | `registry.redhat.io/rhel9/mariadb-1011:1` | `mariadb-data` PVC (5Gi) |

Same stack as `sources/fred-vaughan-cc`, but the database is a **separate**
MariaDB in this namespace (fred's is not shared). The WordPress pod runs under
the `wordpress` ServiceAccount with `anyuid` (Apache binds :80 then drops
privileges); MariaDB runs under the default restricted SCC. This is a **fresh
WordPress install** (no docroot/database to copy); the official image entrypoint
generates `wp-config.php` from the `WORDPRESS_*` env on first boot.

## Database credentials

Credentials live in the `dharmabruce-db` SealedSecret (sclorg `MYSQL_*`
convention; the WordPress Deployment maps them to `WORDPRESS_DB_*`). It is sealed
to the k8s-sno sealed-secrets controller and safe to keep in git. To rotate:

```sh
cat > /tmp/dharmabruce-db.yaml <<'EOF'
apiVersion: v1
kind: Secret
metadata: { name: dharmabruce-db, namespace: dharmabruce }
type: Opaque
stringData:
  MYSQL_DATABASE: wordpress
  MYSQL_USER: dharmabruce
  MYSQL_PASSWORD: <generated-strong-password>
EOF
kubeseal --controller-namespace sealed-secrets --controller-name sealed-secrets \
  -f /tmp/dharmabruce-db.yaml -o yaml > sealed-db-secret.yaml
rm /tmp/dharmabruce-db.yaml
```

## URL / HTTPS handling

`dharmabruce.com` is the canonical host. `WP_HOME`/`WP_SITEURL` are pinned to
`https://dharmabruce.com` via `WORDPRESS_CONFIG_EXTRA`, and the same env tells
WordPress it is behind HTTPS (the edge-terminated Route forwards plain HTTP with
`X-Forwarded-Proto: https`). `www.dharmabruce.com` has its own Route (sharing
the `dharmabruce-com-tls` cert) and is 301'd to the apex by WordPress.

## Content migration (Blogger → WordPress)

The source was a **Google Takeout** of Blogger (2018 schema `feed.atom`), not
the simple "Back up content" XML, and the Takeout bundled three blogs — only
`dharmabruce's Journal` (subdomain `dharmabruce`) is this site. A converter
(`hack/blogger2wxr.py`) turns that `feed.atom` into a WordPress WXR:

- 25 posts (22 published, 3 drafts) + 4 comments + labels (→ tags).
- Permalink slugs are taken from each post's `<blogger:filename>`; set the
  WordPress permalink structure to `/%year%/%monthnum%/%postname%.html` so the
  imported URLs match the originals (`/2008/07/dark-knight-at-imax.html`).
- Every imported post is filed under the **Attic** category, keeping the old
  2006–2024 material out of the main feed while new writing sits up front.
- Author is the `dharmabruce` pseudonym (`dharmabruce@gmail.com`, which forwards
  to the owner).
- Import with image sideloading so media is pulled off `*.blogspot.com` /
  `*.googleusercontent.com` into `wp-content/uploads`.

## Cutover (DNS / TLS)

TLS is handled by cert-manager (`sources/cert-manager`) via the
`letsencrypt-prod` ClusterIssuer. The zone is **not** in Route53, so issuance
uses the ClusterIssuer's **HTTP-01 fallback** solver (DNS-01 is scoped to
`vaughan.cc`). `certificate.yaml` → `dharmabruce-com-tls` (SANs `dharmabruce.com`
+ `www.dharmabruce.com`) stays Pending until DNS resolves to the cluster, then
issues automatically. `router-cert-role{,-binding}.yaml` grant the router read
access to the secret; the Routes carry `externalCertificate`.

DNS at **GoDaddy** (done 2026-06-29):
- `dharmabruce.com` (apex) → **A** → `50.106.17.108` (home public IP fronting
  the k8s-sno router; apex cannot CNAME). **DDNS caveat:** literal IP — update
  if the home IP changes (same as `mountainheart.net`).
- `www.dharmabruce.com` → **CNAME** → `dharmabruce.com`.
- Port 80/443 must reach the OpenShift router from the internet.

Then: wait for `dharmabruce-com-tls` Ready (`oc get certificate -n dharmabruce`),
import content, and verify `https://dharmabruce.com` + the `www` → apex redirect
end-to-end over public DNS.
