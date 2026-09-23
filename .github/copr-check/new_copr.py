import re

def parse(html: str) -> dict:
    downloads: dict[str, int] = {}
    enablements: dict[str, int] = {}
    for row in re.findall(r"<tr\b.*?</tr>", html, re.S):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row))
        release = re.search(r"Fedora [\w.]+", text)
        repo = re.search(r"\((\d+) downloads?\)", text)
        if not (release and repo):
            continue
        rpms = re.findall(r"\((\d+)\)\s*\*", text)
        if not rpms:
            raise ValueError(f"compteur de paquets absent pour {release.group()}")
        downloads[release.group()] = sum(map(int, rpms))
        enablements[release.group()] = int(repo.group(1))
    if not downloads:
        raise ValueError("aucun compteur trouvé (mise en page COPR changée ?)")
    return {
        "total": sum(downloads.values()),
        "by_release": downloads,
        "enablements": sum(enablements.values()),
        "enablements_by_release": enablements,
    }
