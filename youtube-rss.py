import argparse
import json
import os
import re
import time
from typing import Dict, List, Tuple
from yt_dlp import YoutubeDL

RE_PLAYLIST_LINE = re.compile(r'^\s*([^#=\n]+?)\s*=\s*([A-Za-z0-9_-]+)\s*$')


def parse_playlists_from_requirements_md(path: str = "requirements.md") -> List[Tuple[str, str]]:
    """
    Parse playlist names and IDs from requirements.md.
    Expected format after a line that equals '# Playlists' (case-insensitive):
        AEC = PLxxxxxxxxxxxxxxxxxxxx
        PhD Research (assorted) = PLyyyyyyyyyyyyyyyyyyyy
    Returns: list of (name, id)
    """
    if not os.path.exists(path):
        return []

    playlists: List[Tuple[str, str]] = []
    in_section = False
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Detect section start
            if line.lower() == "# playlists":
                in_section = True
                continue

            if not in_section:
                continue

            # Stop if we hit another top-level section
            if line.startswith("# ") and line.lower() != "# playlists":
                break

            if not line or line.startswith("#"):
                continue

            m = RE_PLAYLIST_LINE.match(line)
            if m:
                name, pid = m.group(1).strip(), m.group(2).strip()
                playlists.append((name, pid))
            # silently ignore non-matching lines inside the section

    return playlists


def normalize_playlist_input(arg: str) -> str:
    """Accept either a full URL or a bare playlist ID and return a URL."""
    if arg.startswith("http://") or arg.startswith("https://"):
        return arg
    return f"https://www.youtube.com/playlist?list={arg}"


def fetch_playlist_flat(playlist_url: str, client: str = "web") -> Dict:
    """Fetch a playlist with flat entries (fast, minimal metadata)."""
    ydl_opts = {
        "ignoreerrors": True,
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "no_warnings": True,
        "extract_flat_playlist": True,
        # Extract only fields we want
        "playlist_items": "1-1000",  # Limit for testing
        "extract_info": [
            "id", "title", "channel", "uploader", "uploader_id",
            "channel_id", "uploader_url", "channel_url", "webpage_url",
            "thumbnail", "description", "tags"
        ]
    }
    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(playlist_url, download=False)
            return info or {}
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            return {}


def fetch_video_metadata(id_or_url: str, client: str = "web") -> Dict:
    """
    Fetch minimal metadata for a single YouTube video.
    If video is not readily available, returns empty dict without retrying.
    """
    url = id_or_url if id_or_url.startswith("http") else f"https://www.youtube.com/watch?v={id_or_url}"
    ydl_opts = {
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "no_check_formats": True,
        "writesubtitles": False,
        "writeautomaticsub": False,
        # Only extract the specific fields we need
        "extract_info": [
            "id", "title", "fulltitle", "channel", "uploader", "uploader_id",
            "channel_id", "webpage_url", "thumbnail", "upload_date", 
            "duration", "description", "categories", "tags"
        ]
    }
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info or {}
    except Exception:
        return {}


def save_json(info: Dict, out_dir: str = "data") -> str:
    # Clean the dictionary to only include fields we want
    def clean_dict(d: Dict, is_playlist: bool = False) -> Dict:
        allowed_fields = {
            "id", "title", "fulltitle", "channel", "uploader", "uploader_id",
            "channel_id", "uploader_url", "channel_url", "original_url", "webpage_url",
            "thumbnail", "upload_date", "duration", "duration_string", "description",
            "categories", "tags", "entries"
        }
        result = {}
        for k, v in d.items():
            if k in allowed_fields:
                if k == "entries" and v:
                    result[k] = [clean_dict(e) for e in v if e]
                elif k == "thumbnail" and isinstance(v, list):
                    # Extract highest quality thumbnail URL
                    if v:
                        sorted_thumbs = sorted(v, key=lambda t: t.get("width", 0) * t.get("height", 0), reverse=True)
                        result[k] = sorted_thumbs[0].get("url", "")
                else:
                    result[k] = v
        return result

    # Clean the data
    cleaned = clean_dict(info, is_playlist=True)
    
    # Save to file
    os.makedirs(out_dir, exist_ok=True)
    playlist_id = cleaned.get("id") or "playlist"
    out_path = os.path.join(out_dir, f"{playlist_id}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    return out_path


def format_duration(seconds: int) -> str:
    if not seconds or seconds <= 0:
        return "0:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def best_thumbnail(info: Dict) -> str:
    thumbs = info.get("thumbnails") or []
    if not thumbs:
        return ""
    # Return the URL of the highest resolution thumbnail available
    best = max(thumbs, key=lambda t: t.get("width", 0) * t.get("height", 0))
    return best.get("url", "")


def build_uploader_url(info: Dict) -> str:
    uploader_id = info.get("uploader_id")
    if uploader_id:
        return f"https://www.youtube.com/channel/{uploader_id}"
    return ""


def build_channel_url(info: Dict) -> str:
    channel_id = info.get("channel_id")
    if channel_id:
        return f"https://www.youtube.com/channel/{channel_id}"
    return ""


def minimize_entry(info: Dict) -> Dict:
    # Filter to only include the fields we want
    duration_val = info.get("duration")
    duration_str = info.get("duration_string") or format_duration(duration_val if isinstance(duration_val, int) else 0)
    original = info.get("original_url") or info.get("webpage_url")
    
    # Only include the exact fields we need, nothing more
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "fulltitle": info.get("fulltitle"),
        "channel": info.get("channel"),
        "uploader": info.get("uploader"),
        "uploader_id": info.get("uploader_id"),
        "channel_id": info.get("channel_id"),
        "uploader_url": build_uploader_url(info),
        "channel_url": build_channel_url(info),
        "original_url": original,
        "webpage_url": info.get("webpage_url"),
        "thumbnail": best_thumbnail(info),
        "upload_date": info.get("upload_date"),
        "duration": duration_val,
        "duration_string": duration_str,
        "description": info.get("description"),
        "categories": info.get("categories"),
        "tags": info.get("tags")
    }


def minimize_playlist(info: Dict) -> Dict:
    # Return only the exact fields we want
    entries = []
    for e in (info.get("entries") or []):
        if e:  # Skip None entries
            # Extract only the exact fields we want
            entry = {
                "id": e.get("id", ""),
                "title": e.get("title", ""),
                "fulltitle": e.get("title", ""),  # Use title in fast mode
                "channel": e.get("channel", ""),
                "uploader": e.get("uploader", ""),
                "uploader_id": e.get("uploader_id", ""),
                "channel_id": e.get("channel_id", ""),
                "uploader_url": build_uploader_url(e),
                "channel_url": build_channel_url(e),
                "original_url": e.get("url", ""),
                "webpage_url": e.get("url", ""),
                "thumbnail": best_thumbnail(e),
                "upload_date": e.get("upload_date", ""),
                "duration": e.get("duration", 0),
                "duration_string": format_duration(e.get("duration", 0)),
                "description": e.get("description", ""),
                "categories": [],  # Empty in fast mode
                "tags": []  # Empty in fast mode
            }
            # Remove any None values
            entries.append({k: v for k, v in entry.items() if v is not None})
    
    # Build playlist with exact fields
    playlist = {
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "fulltitle": info.get("title", ""),
        "channel": info.get("channel", ""),
        "uploader": info.get("uploader", ""),
        "uploader_id": info.get("uploader_id", ""),
        "channel_id": info.get("channel_id", ""),
        "uploader_url": build_uploader_url(info),
        "channel_url": build_channel_url(info),
        "thumbnail": best_thumbnail(info),
        "description": info.get("description", ""),
        "categories": info.get("categories", []),
        "tags": info.get("tags", []),
        "entries": entries
    }
    # Remove any None values from playlist level too
    return {k: v for k, v in playlist.items() if v is not None}


def main():
    parser = argparse.ArgumentParser(
        description="Export YouTube playlist metadata to JSON (single playlist or all listed in requirements.md)."
    )
    parser.add_argument("playlist", nargs="?", help="YouTube playlist URL or playlist ID (omit when using --all)")
    parser.add_argument("--all", action="store_true", help="Process all playlists listed in requirements.md")
    parser.add_argument("--req", default="requirements.md", help="Path to requirements.md (default: requirements.md)")
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Fast mode: keep flat entries (no per‑video descriptions/dates)",
    )
    parser.add_argument(
        "--client",
        choices=["android", "web", "tv"],
        default="web",
        help="YouTube player client to use for extraction (default: web)",
    )
    args = parser.parse_args()

    # Decide what to process
    tasks: List[Tuple[str, str]] = []

    if args.all:
        listed = parse_playlists_from_requirements_md(args.req)
        if not listed:
            raise SystemExit(f"No playlists found in {args.req}. Ensure a '# Playlists' section exists.")
        tasks.extend(listed)
    elif args.playlist:
        # Single playlist: name unknown, we’ll use the ID as the name for reporting
        pid = args.playlist if "list=" not in args.playlist else args.playlist.split("list=", 1)[1].split("&", 1)[0]
        tasks.append((pid, args.playlist))
    else:
        parser.error("Provide a PLAYLIST or use --all")

    total_saved = 0
    reports: List[str] = []

    for name, id_or_url in tasks:
        url = normalize_playlist_input(id_or_url)

        # 1) Get flat playlist quickly to enumerate entries and playlist metadata
        playlist_info = fetch_playlist_flat(url, client=args.client)
        if not playlist_info:
            reports.append(f"✗ {name}: failed to fetch")
            continue

        # 2) Optionally try to enrich entries with additional metadata where readily available
        if not args.fast:
            entries = playlist_info.get("entries") or []
            enriched_entries: List[Dict] = []
            try:
                for idx, entry in enumerate(entries, start=1):
                    vid = entry.get("id") or entry.get("url")
                    if not vid:
                        enriched_entries.append(entry)
                        continue
                        
                    full = fetch_video_metadata(vid, client=args.client)
                    if full and full.get("description"):  # Only use full data if we got meaningful metadata
                        enriched_entries.append(full)
                    else:
                        enriched_entries.append(entry)  # Keep original data if full fetch failed

                    if idx % 25 == 0:
                        print(f"...processed {idx} videos")
            except KeyboardInterrupt:
                print(f"\nInterrupted after {len(enriched_entries)} videos; saving partial results...")
                if enriched_entries:
                    playlist_info["entries"] = enriched_entries
                break

            playlist_info["entries"] = enriched_entries

        # 3) Save
        out_path = save_json(playlist_info)
        count = len(playlist_info.get("entries") or [])
        mode = "FAST" if args.fast else "FULL"
        reports.append(f"✓ {name}: {count} items ({mode}) → {out_path}")
        total_saved += 1

    # Summary
    print("\n".join(reports))
    print(f"\nDone. {total_saved}/{len(tasks)} playlist(s) saved.")


if __name__ == "__main__":
    main()