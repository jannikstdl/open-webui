import sqlite3
import chromadb
import re
import itertools
import json
import argparse
import os
import pathlib
import shutil


def get_ids(path):
    database = sqlite3.connect(path)
    cursor = database.cursor()
    cursor.execute("SELECT id FROM segments WHERE scope = 'VECTOR'")
    ids = cursor.fetchall()
    return [id_[0] for id_ in ids]


def main():
    """
    Searches for all files uploaded in chats and knowledges with their
    unique UUID. Can delete the files on disk, in the internal database,
    and/or clean up the chromadb vector storage.

    All deletion steps now run **without interactive confirmation**. Set the
    corresponding --delete-* flags to enable the desired actions.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('-db', '--database-path', type=str,
                        help='Full path to the webui.db file.', required=True)
    parser.add_argument('-b', '--batch-chats', type=int, default=100,
                        help="Number of chats read simultaneously – reduce if low RAM")
    parser.add_argument('-l', '--list-files', action='store_true',
                        help='List files that would be deleted.')
    parser.add_argument('--delete-files', action='store_true',
                        help='Delete orphaned files from the uploads directory.')
    parser.add_argument('--delete-db-entries', action='store_true',
                        help='Delete unused "file" entries from the database.')
    parser.add_argument('--delete-vectors', action='store_true',
                        help='Delete unused entries and folders from the vector storage.')
    args = parser.parse_args()

    # Normalise path and basic validation
    args.database_path = os.path.normpath(args.database_path)
    if not os.path.isfile(args.database_path):
        raise ValueError(f"Database path not pointing to a file: {args.database_path}")

    #################################################
    # File‑ID extraction from knowledges and chats
    #################################################

    conn = sqlite3.connect(args.database_path)
    conn.row_factory = sqlite3.Row  # return dict‑like rows
    cursor = conn.cursor()

    # All unique "file" ids from webui.db
    cursor.execute("SELECT id FROM file")
    webuidb_file_ids = [row['id'] for row in cursor.fetchall()]
    webuidb_file_ids_set = set(webuidb_file_ids)

    # All file ids from knowledges
    cursor.execute("SELECT data FROM knowledge")
    knowledge_rows = [json.loads(row['data']) for row in cursor.fetchall()]
    knowledge_ids = list(itertools.chain(*[list(k.values())[0] for k in knowledge_rows if k is not None]))
    knowledge_ids_set = set(knowledge_ids)

    # All file ids mentioned inside chats (processed in batches)
    cursor.execute("SELECT chat FROM chat")
    chat_file_ids: list[str] = []
    pattern = r'(?<="file": \{"id": ")[a-z0-9\-]*(?=")'  # regex explained in original script
    while True:
        rows = cursor.fetchmany(args.batch_chats)
        if not rows:
            break
        for chat_entry in rows:
            chat_file_ids += list(set(re.findall(pattern, chat_entry['chat'])))
    chat_file_ids_set = set(chat_file_ids)

    # Sanity check: knowledge IDs must not appear in chat uploads
    overlap = chat_file_ids_set.intersection(knowledge_ids_set)
    if overlap:
        raise ValueError(
            f"Found {len(overlap)} knowledge IDs inside chat uploads – this should never happen. IDs: {overlap}")

    # Files referenced either in chat uploads or knowledges
    referenced_ids_set = chat_file_ids_set.union(knowledge_ids_set)

    # Orphaned file entries in DB
    ids_to_delete = webuidb_file_ids_set.difference(referenced_ids_set)

    print(f"Found {len(knowledge_ids_set)} files in knowledge, "
          f"{len(chat_file_ids_set)} files in chat. Total referenced: {len(referenced_ids_set)}")
    print(f"Found {len(webuidb_file_ids_set)} 'file' entries in database; "
          f"{len(ids_to_delete)} can be deleted from DB.")

    #################################################
    # Files on disk (uploads dir)
    #################################################

    uploads_dir = os.path.join(os.path.dirname(args.database_path), 'uploads')
    if not os.path.isdir(uploads_dir):
        raise ValueError(f"Uploads directory not found: {uploads_dir}")

    files: list[str] = os.listdir(uploads_dir)
    files_on_storage_ids: list[str] = [name.split('_')[0] for name in files]
    print(f"Found {len(files_on_storage_ids)} files in uploads directory.")

    files_to_delete: list[str] = []
    unknown_files: list[str] = []
    for file_name, file_id in zip(files, files_on_storage_ids):
        file_path = os.path.join(uploads_dir, file_name)
        if file_id not in referenced_ids_set:
            files_to_delete.append(file_path)
            if file_id not in ids_to_delete:
                unknown_files.append(file_path)

    print(f"{len(files_to_delete)} files can be deleted from storage. "
          f"{len(unknown_files)} of them are unknown to DB.")

    if args.list_files and files_to_delete:
        print("Files to delete:")
        print(*files_to_delete, sep='\n')
        print()

    #################################################
    # Vector store (chromadb)
    #################################################

    chroma_path = os.path.join(os.path.dirname(args.database_path), "vector_db")
    client = chromadb.PersistentClient(chroma_path)
    collections = client.list_collections()

    chroma_file_collections = [c.replace("file-", "") for c in collections if c.startswith("file-")]
    chroma_entries_set = set(chroma_file_collections)
    chroma_entries_to_delete = chroma_entries_set.difference(referenced_ids_set)

    print(f"{len(chroma_entries_to_delete)} vector collections can be deleted.")

    if args.list_files and chroma_entries_to_delete:
        print("Chroma collections to delete:")
        print(*chroma_entries_to_delete, sep='\n')
        print()

    #################################################
    # Deletion steps – NO INTERACTIVE CONFIRMATIONS
    #################################################

    # Delete collections from chromadb
    if chroma_entries_to_delete and args.delete_vectors:
        for collection in chroma_entries_to_delete:
            coll = client.get_collection(f'file-{collection}')
            ids = coll.get()['ids']
            if ids:
                coll.delete(ids)
            del coll
            client.delete_collection(name=f"file-{collection}")
        print(f"Deleted {len(chroma_entries_to_delete)} collections from vector store.")

    # Delete dangling vector folders on disk
    if args.delete_vectors:
        print("Searching for dangling embedding vectors on disk…")
        vector_folders = [x for x in os.listdir(chroma_path) if os.path.isdir(os.path.join(chroma_path, x))]
        held_ids = set(get_ids(os.path.join(chroma_path, "chroma.sqlite3")))
        dangling_folders = set(vector_folders).difference(held_ids)
        if dangling_folders:
            for folder in dangling_folders:
                shutil.rmtree(os.path.join(chroma_path, folder))
            print(f"Deleted {len(dangling_folders)} dangling vector folders.")

    # Delete files from storage
    if files_to_delete and args.delete_files:
        for file_path in files_to_delete:
            os.remove(file_path)
        print(f"Deleted {len(files_to_delete)} files from uploads directory.")

    # Delete orphaned DB entries
    if ids_to_delete and args.delete_db_entries:
        placeholders = ", ".join(["?"] * len(ids_to_delete))
        cursor.execute(f"DELETE FROM file WHERE id IN ({placeholders})", list(ids_to_delete))
        conn.commit()
        print(f"Deleted {len(ids_to_delete)} entries from 'file' table.")

    conn.close()


if __name__ == "__main__":
    main()
