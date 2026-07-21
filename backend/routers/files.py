"""
File operations endpoints.
"""

import os
import mimetypes
import shutil
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from core.dependencies import get_current_user
from services.ownership import require_file_owner

from models.schemas import FileItem, DirectoryListing
from core.config import settings

router = APIRouter(prefix="/api/files", tags=["Files"])


def _resolve_and_validate_path(path: str, must_exist: bool = True) -> str:
    """Resolve a user-supplied path and validate it is within the allowed sandbox.

    All file operations MUST go through this function to prevent path-traversal
    attacks (e.g. /api/files/serve?path=/etc/passwd).

    Allowed roots:
      - The configured work directory (CMBAGENT_DEFAULT_WORK_DIR, default ~/Desktop/cmbdir)
      - /tmp  (for temporary files used during compilation, etc.)

    Raises HTTPException 403 if the resolved path escapes the sandbox.
    Raises HTTPException 404 if must_exist=True and the path doesn't exist.
    """
    if path.startswith("~"):
        path = os.path.expanduser(path)
    # Use realpath to resolve symlinks, preventing symlink-based path traversal
    abs_path = os.path.realpath(path)

    # Determine allowed root directories (use realpath to match the resolved input path,
    # which is critical when /home is a mount or symlink to another filesystem like /Innovation)
    work_dir = os.path.realpath(os.path.expanduser(settings.default_work_dir))
    allowed_roots = [work_dir, os.path.realpath("/tmp")]

    # Also allow the historical default work dir (~/Desktop/cmbdir) so that
    # tasks created before a CMBAGENT_DEFAULT_WORK_DIR change remain accessible.
    legacy_work_dir = os.path.realpath(os.path.expanduser("~/Desktop/cmbdir"))
    if legacy_work_dir != work_dir:
        allowed_roots.append(legacy_work_dir)

    # Check that resolved path is within one of the allowed roots
    if not any(abs_path == root or abs_path.startswith(root + os.sep) for root in allowed_roots):
        raise HTTPException(
            status_code=403,
            detail="Access denied: path is outside the allowed working directory"
        )

    if must_exist and not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="Path not found")

    return abs_path


@router.get("/list")
async def list_directory(path: str = ""):
    """List files and directories in the specified path."""
    try:
        if not path:
            path = os.path.expanduser(settings.default_work_dir)

        path = _resolve_and_validate_path(path)

        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        items = []
        try:
            for item_name in sorted(os.listdir(path)):
                item_path = os.path.join(path, item_name)

                # Skip hidden files
                if item_name.startswith('.'):
                    continue

                try:
                    stat_info = os.stat(item_path)
                except (FileNotFoundError, OSError):
                    continue  # Skip broken symlinks or vanished files

                is_dir = os.path.isdir(item_path)

                file_item = FileItem(
                    name=item_name,
                    path=item_path,
                    type="directory" if is_dir else "file",
                    size=None if is_dir else stat_info.st_size,
                    modified=stat_info.st_mtime,
                    mime_type=None if is_dir else mimetypes.guess_type(item_path)[0]
                )
                items.append(file_item)
        except PermissionError:
            raise HTTPException(status_code=403, detail="Permission denied")

        # Get parent directory
        parent = os.path.dirname(path) if path != "/" else None

        return DirectoryListing(
            path=path,
            items=items,
            parent=parent
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/content")
async def get_file_content(path: str):
    """Get the content of a file."""
    try:
        path = _resolve_and_validate_path(path)

        if not os.path.isfile(path):
            raise HTTPException(status_code=400, detail="Path is not a file")

        # Check file size
        file_size = os.path.getsize(path)
        max_size = settings.max_file_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(status_code=413, detail="File too large")

        # Try to read as text first
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {
                "path": path,
                "content": content,
                "type": "text",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0]
            }
        except UnicodeDecodeError:
            # If it's not text, return file info only
            return {
                "path": path,
                "content": None,
                "type": "binary",
                "size": file_size,
                "mime_type": mimetypes.guess_type(path)[0],
                "message": "Binary file - content not displayed"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/content")
async def save_file_content(path: str, body: dict):
    """Save text content to a file."""
    try:
        abs_path = _resolve_and_validate_path(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=400, detail="Path is not a file")
        content = body.get("content")
        if content is None:
            raise HTTPException(status_code=400, detail="Missing 'content' in request body")
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": abs_path, "size": os.path.getsize(abs_path)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear-directory")
async def clear_directory(path: str):
    """Clear all contents of a directory."""
    try:
        abs_path = _resolve_and_validate_path(path)

        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # Count items before deletion
        items_deleted = 0

        # Remove all contents
        for item in os.listdir(abs_path):
            item_path = os.path.join(abs_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
            items_deleted += 1

        return {
            "message": f"Successfully cleared directory: {path}",
            "items_deleted": items_deleted,
            "path": abs_path
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing directory: {str(e)}")


@router.get("/images")
async def get_images(work_dir: str):
    """Get all image files from the working directory."""
    try:
        try:
            abs_path = _resolve_and_validate_path(work_dir)
        except HTTPException:
            return {"images": [], "message": "Working directory not found or not accessible"}

        if not os.path.isdir(abs_path):
            return {"images": [], "message": "Working directory not found"}

        # Common image extensions
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}

        images = []

        # Recursively search for image files
        for root, dirs, files in os.walk(abs_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in files:
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()

                if file_ext in image_extensions:
                    # Get relative path from work_dir
                    rel_path = os.path.relpath(file_path, abs_path)

                    # Get file stats
                    stat = os.stat(file_path)

                    images.append({
                        "name": file,
                        "path": file_path,
                        "relative_path": rel_path,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "extension": file_ext,
                        "directory": os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                    })

        # Sort by modification time (newest first)
        images.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "work_dir": work_dir,
            "images": images,
            "count": len(images)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scanning for images: {str(e)}")


@router.get("/serve-image")
async def serve_image(path: str):
    """Serve an image file."""
    try:
        abs_path = _resolve_and_validate_path(path)

        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="Image file not found")

        # Check if it's an image file
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tiff', '.tif'}
        file_ext = os.path.splitext(abs_path)[1].lower()

        if file_ext not in image_extensions:
            raise HTTPException(status_code=400, detail="File is not an image")

        # Determine MIME type
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml',
            '.webp': 'image/webp',
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff'
        }

        mime_type = mime_types.get(file_ext, 'application/octet-stream')

        # Return the file
        return FileResponse(abs_path, media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.get("/info")
async def file_info(path: str):
    """Return file metadata (size, mime type) without reading content."""
    try:
        abs_path = _resolve_and_validate_path(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="File not found")
        stat = os.stat(abs_path)
        return {
            "path": abs_path,
            "name": os.path.basename(abs_path),
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "mime_type": mimetypes.guess_type(abs_path)[0],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/serve")
async def serve_file(path: str):
    """Serve a file inline with its proper MIME type (for browser viewing)."""
    try:
        abs_path = _resolve_and_validate_path(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="File not found")
        mime_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
        return FileResponse(abs_path, media_type=mime_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download")
async def download_file(path: str):
    """Download a file as an attachment."""
    try:
        abs_path = _resolve_and_validate_path(path)
        if not os.path.isfile(abs_path):
            raise HTTPException(status_code=404, detail="File not found")
        mime_type = mimetypes.guess_type(abs_path)[0] or "application/octet-stream"
        filename = os.path.basename(abs_path)
        # Escape quotes in filename to prevent header injection
        safe_filename = filename.replace('\\', '\\\\').replace('"', '\\"')
        return FileResponse(
            abs_path,
            media_type=mime_type,
            headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/find")
async def find_file(directory: str, filename: str):
    """Recursively search for a file by name within a directory."""
    try:
        abs_dir = _resolve_and_validate_path(directory)

        if not os.path.isdir(abs_dir):
            raise HTTPException(status_code=400, detail="Path is not a directory")

        # Sanitize filename to prevent path traversal
        safe_filename = os.path.basename(filename)
        if not safe_filename or safe_filename.startswith('.'):
            raise HTTPException(status_code=400, detail="Invalid filename")

        matches = []
        for root, dirs, files in os.walk(abs_dir):
            # Skip hidden directories (e.g. .git)
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for f in files:
                if f == safe_filename:
                    full_path = os.path.join(root, f)
                    stat = os.stat(full_path)
                    matches.append({
                        "name": f,
                        "path": full_path,
                        "relative_path": os.path.relpath(full_path, abs_dir),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    })

        # Sort by modification time (newest first)
        matches.sort(key=lambda x: x['modified'], reverse=True)

        return {
            "directory": abs_dir,
            "filename": safe_filename,
            "matches": matches,
            "count": len(matches),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding file: {str(e)}")


# Allowed extensions for file upload
_UPLOAD_ALLOWED_EXTENSIONS = {
    '.csv', '.txt', '.md', '.json', '.fits', '.npy',
    '.h5', '.hdf5', '.dat', '.tsv', '.xlsx', '.xls',
    '.png', '.jpg', '.jpeg', '.pdf',
    '.docx', '.doc',  # Word documents
}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    task_id: str = Form(...),
    subfolder: str = Form("input_files"),
    current_user=Depends(get_current_user),
):
    """Upload a file for a Deepresearch research task.

    Files are stored in {work_dir}/deepresearch_tasks/{task_id}/{subfolder}/.
    """
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _UPLOAD_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File extension '{ext}' not allowed. Allowed: {sorted(_UPLOAD_ALLOWED_EXTENSIONS)}"
        )

    # Prevent path traversal in filename
    safe_name = os.path.basename(file.filename or "upload")
    if not safe_name or safe_name.startswith('.'):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Prevent path traversal in subfolder
    safe_subfolder = os.path.normpath(subfolder).lstrip(os.sep)
    if ".." in safe_subfolder:
        raise HTTPException(status_code=400, detail="Invalid subfolder path")

    # Check Content-Length header first to reject oversized uploads early
    max_size = settings.max_file_size_mb * 1024 * 1024
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_file_size_mb}MB"
        )

    # Build target directory
    # Look up the task's actual work_dir from the database first (for session-based paths)
    target_dir = None
    try:
        from cmbagent.database.base import get_db_session
        from cmbagent.database.models import WorkflowRun
        db = get_db_session()
        try:
            require_file_owner(task_id, current_user, db)
            run = db.query(WorkflowRun).filter(WorkflowRun.id == task_id).first()
            if run and run.meta and run.meta.get("work_dir"):
                work_dir_from_db = run.meta["work_dir"]
                target_dir = os.path.join(work_dir_from_db, safe_subfolder)
        finally:
            db.close()
    except Exception:
        pass  # Fall through to legacy path

    if not target_dir:
        # Legacy fallback for tasks created before session-based paths
        base_work_dir = os.path.expanduser(settings.default_work_dir)
        target_dir = os.path.join(base_work_dir, "deepresearch_tasks", task_id, safe_subfolder)

    # Validate the target directory is within the sandbox
    _resolve_and_validate_path(target_dir, must_exist=False)
    os.makedirs(target_dir, exist_ok=True)

    target_path = os.path.join(target_dir, safe_name)

    # Read and validate actual size (defense-in-depth: Content-Length can be spoofed)
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_file_size_mb}MB"
        )

    # Write file
    with open(target_path, "wb") as f:
        f.write(contents)

    # Extract text from PDFs so frontend can auto-populate the RFP content field
    extracted_text = None
    if ext == '.pdf':
        try:
            from services.pdf_extractor import extract_pdf_content
            extracted_text = extract_pdf_content(target_path)
        except Exception:
            pass

    resp = {
        "filename": safe_name,
        "path": target_path,
        "size": len(contents),
        "task_id": task_id,
        "subfolder": safe_subfolder,
    }
    if extracted_text is not None:
        resp["extracted_text"] = extracted_text
    return resp
