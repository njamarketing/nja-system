"""Authenticated, bounded Google Drive thumbnail proxy. No disk cache."""
import base64
import io
import re
import warnings
from urllib.parse import urlsplit, urljoin, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from PIL import Image


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def google_thumbnail_url(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower()
        return (p.scheme == 'https' and not p.username and not p.password
                and p.port in (None, 443)
                and (host == 'googleusercontent.com' or host.endswith('.googleusercontent.com')))
    except ValueError:
        return False


def fetch_thumbnail(url, token):
    opener = build_opener(NoRedirect())
    for _ in range(4):
        if not google_thumbnail_url(url):
            return None
        try:
            with opener.open(Request(url, headers={'Authorization': 'Bearer ' + token}), timeout=15) as r:
                raw = r.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                return None
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as im:
                    if im.width * im.height > 20_000_000:
                        return None
                    im.thumbnail((480, 360))
                    im = im.convert('RGBA')
                    out = io.BytesIO()
                    im.save(out, format='PNG')
            return base64.b64encode(out.getvalue()).decode()
        except HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                url = urljoin(url, e.headers.get('Location', ''))
                continue
            return None
        except (URLError, TimeoutError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            return None
    return None


def api(a, c, u, method, path):
    if method != 'GET' or not path.startswith('/api/drive/thumbnail/'):
        return None
    a.need(u, 'drive')
    fid = path.removeprefix('/api/drive/thumbnail/')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', fid):
        raise a.Error(400, 'Arquivo inválido.')
    import integrations
    token = integrations.drive_token(a, c, u)
    # Google checks this user's access on EVERY request, before fetching any preview.
    meta = integrations.external(a, 'https://www.googleapis.com/drive/v3/files/' + fid + '?' + urlencode({
        'fields': 'thumbnailLink', 'supportsAllDrives': 'true'
    }), headers={'Authorization': 'Bearer ' + token})
    data = fetch_thumbnail(meta.get('thumbnailLink', ''), token)
    return {'data': data, 'mime': 'image/png' if data else None}
