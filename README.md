# network-lab-image

Images OCI génériques pour les laboratoires de réseautique de LOG100.

Ce dépôt contient volontairement des **environnements de service génériques pour le
cours**, et non des réponses ou des configurations propres à un laboratoire. Chaque dépôt
`network-labN-*` doit monter ses propres zones DNS, sa configuration Web, ses certificats,
ses données et ses fichiers d’expérience dans ces images.

## Images

| Répertoire | Paquet GHCR | Rôle |
|---|---|---|
| `images/toolbox` | `log100-net-toolbox` | Outils en ligne de commande pour l’observation et le diagnostic réseau |
| `images/web` | `log100-net-web` | Point de terminaison HTTP/HTTPS local et contrôlé |
| `images/dns` | `log100-net-dns` | Service DNS BIND local et contrôlé |

Le premier pilote évite volontairement les images de routeur ou de NAT. Elles ne devraient
être ajoutées qu’après que `labctl doctor` aura permis de caractériser précisément ce que
la configuration Podman sans privilèges de l’ÉTS autorise réellement.

## Construction locale avec Podman

```bash
./scripts/build-local.sh
```

Cette commande produit :

```text
localhost/log100-net-toolbox:dev
localhost/log100-net-web:dev
localhost/log100-net-dns:dev
```

Exécutez ensuite :

```bash
./scripts/smoke-test.sh
```

Le test de fumée crée un réseau temporaire défini par l’utilisateur, démarre les trois
images sans mode privilégié ni réseau de l’hôte, vérifie HTTP et DNS depuis l’image
`toolbox`, puis supprime les ressources créées.

## Publication sur GHCR

Le flux GitHub Actions construit les trois images à l’aide d’une matrice et les publie
vers :

```text
ghcr.io/<organization>/log100-net-toolbox
ghcr.io/<organization>/log100-net-web
ghcr.io/<organization>/log100-net-dns
```

Le flux s’authentifie auprès de GHCR avec le `GITHUB_TOKEN` du dépôt et nécessite la
permission `packages: write`. Le registre de conteneurs GitHub permet le téléchargement
anonyme des paquets publics; ces images de cours peuvent donc être publiques même si les
dépôts réservés aux enseignants demeurent privés.

Politique de publication recommandée :

- `edge` : branche principale courante, utile pendant le développement des laboratoires;
- `vX.Y.Z` : images publiées pour une version ou une session;
- `sha-...` : traçabilité immuable de l’intégration continue;
- **les dépôts de laboratoires utilisent un digest** pour les versions évaluées.

Par exemple :

```text
ghcr.io/<organization>/log100-net-toolbox@sha256:...
```

## Personnalisation propre à un laboratoire

Il n’est pas nécessaire de reconstruire une image simplement pour modifier une question
ou une configuration de laboratoire. Privilégiez les montages de répertoires :

```bash
podman run ... \
  -v "$PWD/config/web:/etc/nginx/lab:ro,Z" \
  ghcr.io/<organization>/log100-net-web@sha256:...
```

ou :

```bash
podman run ... \
  -v "$PWD/config/dns:/etc/bind/lab:ro,Z" \
  ghcr.io/<organization>/log100-net-dns@sha256:...
```

L’option `:Z` de réétiquetage SELinux peut être omise sur les postes Ubuntu de l’ÉTS si
SELinux n’y est pas utilisé. Les fonctions d’extension des laboratoires doivent choisir la
syntaxe de montage correspondant à l’environnement qui aura été validé sur les postes de
laboratoire.

## Politique concernant l’image de base

Les images initiales utilisent Ubuntu 24.04 LTS, un choix stable et familier dans le
contexte de l’ÉTS. Les `Containerfile` exposent `BASE_IMAGE` comme argument de construction
afin que l’intégration continue puisse éventuellement épingler un digest Ubuntu sans
modifier chaque fichier.

Pour une version utilisée pendant une session, résolvez et consignez le digest de l’image
de base, puis épinglez également par digest les images LOG100 utilisées dans chaque dépôt
de laboratoire.
