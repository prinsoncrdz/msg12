import os
import json
import time
import re
from datetime import datetime, timezone

# Import cloudinary modules conditionally or handle missing package gracefully
try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    CLOUDINARY_AVAILABLE = True
except ImportError:
    CLOUDINARY_AVAILABLE = False

import tempfile

def _get_local_backup_dir():
    """Returns a writable directory for temporary local caching (e.g. /tmp on Vercel/Linux)."""
    tmp_dir = os.path.join(tempfile.gettempdir(), 'msg_loc_backups')
    try:
        os.makedirs(tmp_dir, exist_ok=True)
        return tmp_dir
    except Exception:
        return tempfile.gettempdir()

def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, val = line.split('=', 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass

def is_cloudinary_configured():
    """Return True if Cloudinary environment variables are set and package is available."""
    if not CLOUDINARY_AVAILABLE:
        return False
    
    _load_env_file()
    
    url = os.environ.get('CLOUDINARY_URL')
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')

    if url or (cloud_name and api_key and api_secret):
        try:
            if url:
                cloudinary.config()
            else:
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret,
                    secure=True
                )
            return True
        except Exception:
            return False
    return False

def _sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', str(name or 'document'))

def save_summary_backup(metadata, items, user_email="info@msgoilfield.com", pdf_b64=None):
    """
    Saves a summary sheet backup to Cloudinary (if configured) and local backup store.
    Returns dictionary with backup info.
    """
    po_num = metadata.get('po_number', 'NO_PO').strip()
    client = metadata.get('to_client', 'Unknown_Client').strip()
    msg_ref = metadata.get('msg_ref', '').strip()
    date_str = metadata.get('date', '').strip()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    
    clean_po = _sanitize_filename(po_num)
    backup_id = f"backup_{clean_po}_{timestamp}"
    saved_at = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    backup_data = {
        'backup_id': backup_id,
        'po_number': po_num,
        'client': client,
        'msg_ref': msg_ref,
        'date': date_str,
        'metadata': metadata,
        'items': items,
        'item_count': len(items),
        'saved_at': saved_at,
        'saved_by': user_email,
        'pdf_b64': pdf_b64
    }

    # 1. Save locally (wrapped in try-except for read-only filesystem safety on Vercel)
    try:
        backup_dir = _get_local_backup_dir()
        local_path = os.path.join(backup_dir, f"{backup_id}.json")
        with open(local_path, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
    except Exception:
        pass

    cloudinary_status = "not_configured"
    cloudinary_public_id = None
    cloudinary_url = None

    # 2. Save to Cloudinary if configured
    if is_cloudinary_configured():
        try:
            cloud_public_id = f"msg_loc_backups/{backup_id}"
            json_bytes = json.dumps(backup_data, indent=2).encode('utf-8')

            # Upload raw file
            upload_res = cloudinary.uploader.upload(
                json_bytes,
                resource_type='raw',
                public_id=cloud_public_id,
                overwrite=True,
                tags=['msg_loc_backup', f"po_{clean_po}"],
                context={
                    'po_number': po_num,
                    'client': client,
                    'msg_ref': msg_ref,
                    'date': date_str,
                    'item_count': str(len(items)),
                    'saved_at': saved_at
                }
            )
            cloudinary_status = "saved"
            cloudinary_public_id = upload_res.get('public_id')
            cloudinary_url = upload_res.get('secure_url')
        except Exception as e:
            cloudinary_status = f"error: {str(e)}"

    return {
        'success': True,
        'backup_id': backup_id,
        'po_number': po_num,
        'client': client,
        'saved_at': saved_at,
        'item_count': len(items),
        'cloudinary_status': cloudinary_status,
        'cloudinary_public_id': cloudinary_public_id,
        'cloudinary_url': cloudinary_url
    }

def search_summary_backups(query=""):
    """
    Search backup summary sheets from Cloudinary and local backup store.
    """
    query = (query or "").strip().lower()
    results = []
    seen_ids = set()

    # 1. Search Cloudinary if configured
    if is_cloudinary_configured():
        try:
            # Use Cloudinary resources_by_tag or search API
            c_res = cloudinary.api.resources_by_tag(
                'msg_loc_backup',
                resource_type='raw',
                context=True,
                max_results=50
            )
            for res in c_res.get('resources', []):
                pid = res.get('public_id')
                ctx = res.get('context', {}).get('custom', {})
                po_number = ctx.get('po_number', pid)
                client = ctx.get('client', '')
                msg_ref = ctx.get('msg_ref', '')
                date_str = ctx.get('date', '')
                saved_at = ctx.get('saved_at', res.get('created_at', ''))

                match = True
                if query:
                    searchable = f"{po_number} {client} {msg_ref} {date_str} {pid}".lower()
                    match = query in searchable

                if match:
                    backup_id = pid.replace('msg_loc_backups/', '')
                    results.append({
                        'backup_id': backup_id,
                        'cloudinary_public_id': pid,
                        'po_number': po_number,
                        'client': client,
                        'msg_ref': msg_ref,
                        'date': date_str,
                        'saved_at': saved_at,
                        'source': 'cloudinary',
                        'url': res.get('secure_url')
                    })
                    seen_ids.add(backup_id)
        except Exception:
            pass

    # 2. Search local backup store (wrapped safely in try-except)
    try:
        local_dir = _get_local_backup_dir()
        if os.path.exists(local_dir):
            for fname in os.listdir(local_dir):
                if fname.endswith('.json'):
                    fpath = os.path.join(local_dir, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        b_id = data.get('backup_id', fname.replace('.json', ''))
                        if b_id in seen_ids:
                            continue

                        po_num = data.get('po_number', '')
                        client = data.get('client', '')
                        msg_ref = data.get('msg_ref', '')
                        date_str = data.get('date', '')
                        saved_at = data.get('saved_at', '')
                        items = data.get('items', [])

                        items_text = " ".join([str(it.get('description', '')) + " " + str(it.get('remarks', '')) for it in items])

                        match = True
                        if query:
                            searchable = f"{po_num} {client} {msg_ref} {date_str} {items_text} {b_id}".lower()
                            match = query in searchable

                        if match:
                            results.append({
                                'backup_id': b_id,
                                'cloudinary_public_id': None,
                                'po_number': po_num,
                                'client': client,
                                'msg_ref': msg_ref,
                                'date': date_str,
                                'saved_at': saved_at,
                                'item_count': len(items),
                                'source': 'local'
                            })
                    except Exception:
                        continue
    except Exception:
        pass

    # Sort results by saved_at descending
    results.sort(key=lambda x: str(x.get('saved_at', '')), reverse=True)
    return results

def restore_summary_backup(backup_id):
    """
    Fetch raw JSON summary sheet backup data from Cloudinary or local backup store.
    """
    # 1. Check local backup store first (safely wrapped)
    try:
        local_dir = _get_local_backup_dir()
        local_path = os.path.join(local_dir, f"{backup_id}.json")
        if not local_path.endswith('.json'):
            local_path += '.json'

        if os.path.exists(local_path):
            with open(local_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass

    # 2. Try fetching from Cloudinary if configured
    if is_cloudinary_configured():
        try:
            cloud_public_id = backup_id
            if not cloud_public_id.startswith('msg_loc_backups/'):
                cloud_public_id = f"msg_loc_backups/{backup_id}"

            res = cloudinary.api.resource(cloud_public_id, resource_type='raw')
            url = res.get('secure_url')
            if url:
                import urllib.request
                req = urllib.request.urlopen(url)
                content = req.read().decode('utf-8')
                return json.loads(content)
        except Exception as e:
            raise ValueError(f"Failed to fetch Cloudinary backup '{backup_id}': {str(e)}")

    raise ValueError(f"Backup '{backup_id}' not found locally or on Cloudinary.")

def delete_summary_backup(backup_id):
    """
    Delete backup from Cloudinary and local store.
    """
    deleted_local = False
    deleted_cloud = False

    try:
        local_dir = _get_local_backup_dir()
        local_path = os.path.join(local_dir, f"{backup_id}.json")
        if os.path.exists(local_path):
            os.remove(local_path)
            deleted_local = True
    except Exception:
        pass

    if is_cloudinary_configured():
        try:
            cloud_public_id = backup_id
            if not cloud_public_id.startswith('msg_loc_backups/'):
                cloud_public_id = f"msg_loc_backups/{backup_id}"
            cloudinary.uploader.destroy(cloud_public_id, resource_type='raw')
            deleted_cloud = True
        except Exception:
            pass

    return {'success': True, 'deleted_local': deleted_local, 'deleted_cloud': deleted_cloud}
