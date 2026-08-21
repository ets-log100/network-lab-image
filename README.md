# network-lab-image

Images OCI génériques pour les laboratoires de réseautique de LOG100.

Ce dépôt contient des environnements génériques pour le cours, et non des réponses ou des configurations propres à un laboratoire. Les dépôts `network-labN-*` fournissent les scénarios, les fichiers de configuration et les données nécessaires à chaque expérience.

## Images

| Répertoire | Paquet GHCR | Rôle |
|---|---|---|
| `images/toolbox` | `log100-net-toolbox` | Outils de mesure et de diagnostic; inclut `netprobe` et `udp-echo` |
| `images/web` | `log100-net-web` | Point de terminaison HTTP/HTTPS local et contrôlé |
| `images/dns` | `log100-net-dns` | Service DNS BIND local et contrôlé |
| `images/link` | `log100-net-link` | Émulation de conditions réseau TCP/UDP en espace utilisateur |
| `images/router` | `log100-net-router` | Boîte à outils réseau avec FRRouting pour les expériences OSPF |

## L'image `log100-net-link`

`log100-net-link` relaie des flux TCP et des datagrammes UDP entre deux réseaux Podman et applique des conditions contrôlées.

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

La capacité est appliquée aux flux TCP et aux datagrammes transférés. La perte configurée s'applique uniquement aux datagrammes UDP dans le sens client vers service.

## L'image `log100-net-router`

`log100-net-router` dérive de `log100-net-toolbox` et ajoute FRRouting. Les démons `zebra` et `ospfd` sont activés dans `/etc/frr/daemons`.

Les configurations OSPF propres aux laboratoires ne sont pas intégrées à l'image. Elles sont copiées dans les conteneurs depuis le dépôt du laboratoire avant le démarrage de FRRouting.

Cette séparation permet de réutiliser la même image de routeur pour plusieurs topologies.

## Outils supplémentaires dans `toolbox`

### `netprobe`

`netprobe` envoie de petites sondes UDP à un service d'écho et rapporte le nombre de sondes, la perte, le RTT et une mesure simple de variation.

### `udp-echo`

Serveur d'écho UDP minimal :

```bash
udp-echo --port 7000
```

## Construction locale avec Podman

```bash
./scripts/build-local.sh
```

Cette commande produit les images locales `localhost/log100-net-*:dev`, y compris `localhost/log100-net-router:dev`.

Exécutez ensuite :

```bash
./scripts/smoke-test.sh
```

## Publication sur GHCR

Le flux GitHub Actions construit les images et les publie vers `ghcr.io/<organization>/log100-net-*`.

Politique de publication recommandée :

- `edge` : branche principale courante;
- `vX.Y.Z` : version publiée;
- `sha-...` : traçabilité de l'intégration continue;
- les laboratoires évalués utilisent un digest OCI immuable.

Exemple :

```text
ghcr.io/<organization>/log100-net-router@sha256:...
```

## Politique concernant les privilèges

Les images de base de ce dépôt doivent fonctionner avec Podman rootless. Toute image nécessitant une capacité supplémentaire doit être documentée et validée sur les postes ÉTS avant d'être utilisée dans un laboratoire évalué.

`log100-net-router` est destiné à être lancé avec les capacités `NET_RAW` et `NET_ADMIN`, sans mode `--privileged`.
