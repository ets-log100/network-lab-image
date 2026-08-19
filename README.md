# network-lab-image

Images OCI génériques pour les laboratoires de réseautique de LOG100.

Ce dépôt contient des **environnements génériques pour le cours**, et non des réponses ou des configurations propres à un laboratoire. Les dépôts `network-labN-*` fournissent les scénarios, les fichiers de configuration et les données nécessaires à chaque expérience.

## Images

| Répertoire | Paquet GHCR | Rôle |
|---|---|---|
| `images/toolbox` | `log100-net-toolbox` | Outils de mesure et de diagnostic; inclut `netprobe` et `udp-echo` |
| `images/web` | `log100-net-web` | Point de terminaison HTTP/HTTPS local et contrôlé |
| `images/dns` | `log100-net-dns` | Service DNS BIND local et contrôlé |
| `images/link` | `log100-net-link` | Émulation de conditions réseau TCP/UDP en espace utilisateur |

## L’image `log100-net-link`

`log100-net-link` est conçue pour les postes ÉTS utilisant Podman sans privilèges. Elle **ne configure pas `tc`, `netem`, `nftables` ni les interfaces du noyau**. Elle relaie plutôt des flux TCP et des datagrammes UDP entre deux réseaux Podman et applique des conditions contrôlées en espace utilisateur.

Paramètres principaux :

```text
LINK_TCP_MAPS=5201=server:5201,8080=web:8080
LINK_UDP_MAPS=7000=server:7000
LINK_DELAY_MS=20
LINK_JITTER_MS=5
LINK_BANDWIDTH_MBIT=10
LINK_UDP_LOSS_PERCENT=2
LINK_SEED=1001
```

La capacité est appliquée aux flux TCP et aux datagrammes transférés. La perte configurée s’applique uniquement aux datagrammes UDP dans le sens client → service; elle sert à produire une expérience de perte contrôlée sans prétendre émuler exactement la file d’attente d’une interface physique.

Le délai est appliqué dans chaque direction. Ainsi, une configuration de `20 ms` produit normalement un RTT applicatif proche de `40 ms`, auquel s’ajoutent les délais d’exécution locaux.

Cette image vise la **reproductibilité pédagogique**, pas la fidélité d’un émulateur de réseau de recherche. Les laboratoires doivent l’indiquer explicitement lorsqu’ils interprètent les mesures.

## Outils supplémentaires dans `toolbox`

### `netprobe`

`netprobe` envoie de petites sondes UDP à un service d’écho et rapporte :

- nombre de sondes envoyées et reçues;
- pourcentage de perte;
- RTT minimum, moyen et maximum;
- variation moyenne absolue entre deux RTT successifs.

Exemple :

```bash
netprobe link --count 20 --json
```

### `udp-echo`

Serveur d’écho UDP minimal utilisé derrière `log100-net-link` :

```bash
udp-echo --port 7000
```

## Construction locale avec Podman

```bash
./scripts/build-local.sh
```

Cette commande produit :

```text
localhost/log100-net-toolbox:dev
localhost/log100-net-web:dev
localhost/log100-net-dns:dev
localhost/log100-net-link:dev
```

Exécutez ensuite :

```bash
./scripts/smoke-test.sh
```

Le test crée deux réseaux Podman, place `log100-net-link` entre le client et les services, puis vérifie HTTP, les sondes UDP, le débit TCP et DNS sans utiliser le mode privilégié.

## Publication sur GHCR

Le flux GitHub Actions construit les quatre images à l’aide d’une matrice et les publie vers :

```text
ghcr.io/<organization>/log100-net-toolbox
ghcr.io/<organization>/log100-net-web
ghcr.io/<organization>/log100-net-dns
ghcr.io/<organization>/log100-net-link
```

Politique de publication recommandée :

- `edge` : branche principale courante;
- `vX.Y.Z` : version publiée;
- `sha-...` : traçabilité de l’intégration continue;
- les laboratoires évalués utilisent idéalement un **digest OCI immuable**.

Exemple :

```text
ghcr.io/<organization>/log100-net-link@sha256:...
```

## Politique concernant les privilèges

Les images de base de ce dépôt doivent fonctionner avec Podman rootless. Toute future image nécessitant une capacité supplémentaire doit être documentée et validée sur les postes ÉTS avant d’être utilisée dans un laboratoire évalué.
