# Privacy Policy — PDF-Equilibrist

*[Version française plus bas](#politique-de-confidentialité)*

PDF-Equilibrist is a local desktop application, free and open source (GPLv3).
Your documents are processed on your computer and are **never** sent anywhere.
There is no telemetry, no analytics, no account and no online activation.

## Network connections

The application can contact exactly two online services. Neither ever receives
the content of a document, and both can be blocked (see below).

| Service | Endpoint | When | What is sent |
|---|---|---|---|
| GitHub | `api.github.com` | At startup, if "Check for updates at startup" is enabled (default on Windows only), and when you open *Help › Check for Updates* or *Help › About PDF-Equilibrist* | Nothing: the version comparison happens on your computer. Clicking *Download and install* (Windows) downloads the installer from GitHub. |
| OSV.dev | `api.osv.dev` | Only when you run *Help › Check CVE Vulnerabilities* | The names and versions of the libraries used by the application |

Like any Internet request, these connections expose your IP address to the
service contacted. Whenever the application connects, it says so on screen and
names the service.

On Linux (AUR, PPA, COPR, Flatpak), the startup check is disabled by default:
updates are handled by your package manager. On Flatpak it is never run.

## Blocking all connections

*Help › Internet connections › Block all Internet connections* stops every
request before it is sent — the block is enforced in a single place in the code
(`src/pdf_equilibrist/network.py`), not just by hiding buttons. The CVE check
then only runs its local source analysis (Bandit).

## Links inside PDF files

Clicking a web link inside a PDF shows the full address and asks for
confirmation. If you accept, your web browser — not PDF-Equilibrist — opens it.

---

## Politique de confidentialité

PDF-Equilibrist est une application de bureau locale, libre et gratuite (GPLv3).
Vos documents sont traités sur votre ordinateur et ne sont **jamais** envoyés
nulle part. Aucune télémétrie, aucune statistique d'usage, aucun compte, aucune
activation en ligne.

### Connexions réseau

L'application peut contacter exactement deux services en ligne. Aucun ne reçoit
jamais le contenu d'un document, et les deux peuvent être bloqués (voir plus bas).

| Service | Point d'accès | Quand | Ce qui est envoyé |
|---|---|---|---|
| GitHub | `api.github.com` | Au démarrage si « Vérifier les mises à jour au démarrage » est coché (par défaut sous Windows uniquement), et à l'ouverture de *Aide › Vérifier les mises à jour* ou *Aide › À propos de PDF-Equilibrist* | Rien : la comparaison de version se fait sur votre ordinateur. Le bouton *Télécharger et installer* (Windows) télécharge l'installeur depuis GitHub. |
| OSV.dev | `api.osv.dev` | Uniquement quand vous lancez *Aide › Vérifier les vulnérabilités CVE* | Les noms et versions des bibliothèques utilisées par l'application |

Comme toute requête Internet, ces connexions exposent votre adresse IP au service
contacté. Chaque fois que l'application se connecte, elle l'indique à l'écran en
nommant le service.

Sous Linux (AUR, PPA, COPR, Flatpak), la vérification au démarrage est désactivée
par défaut : les mises à jour relèvent du gestionnaire de paquets. Sous Flatpak,
elle n'est jamais lancée.

### Bloquer toutes les connexions

*Aide › Connexions Internet › Bloquer toutes les connexions Internet* arrête
chaque requête avant son envoi — le blocage est appliqué à un seul endroit du
code (`src/pdf_equilibrist/network.py`), pas seulement en masquant des boutons.
La vérification CVE se limite alors à l'analyse locale du code (Bandit).

### Liens contenus dans les PDF

Un clic sur un lien web d'un PDF affiche l'adresse complète et demande
confirmation. Si vous acceptez, c'est votre navigateur — pas PDF-Equilibrist —
qui l'ouvre.
