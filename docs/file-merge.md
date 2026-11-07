---
title: Merge duplicate files
description: Tick duplicate files in the File Manager, or open one, choose the file to keep, and every document that used the others uses it instead; the others and their content are removed.
nav_title: Merge files
order: 7
updated: 2026-11-07
---

File merge folds duplicate File records into one, for example the same logo uploaded five times to five Items. Every document that used one of the duplicates uses the file you keep instead, and the duplicates are removed, along with their content once nothing uses it.

Frappe's own rename-and-merge, which [bulk merge](merge-records.md) uses, is not enough for files: documents refer to a file by its URL, such as `/files/logo.png`, in an Attach field or in the HTML of a text field, not by the File record's name. File merge rewrites those URLs.

## Before you start

- A System Manager must tick **Allow File Merge** in **Data Steward Settings**. See [Configuration](configuration.md).
- You need the System Manager role, write permission on the file you keep and delete permission on each file you merge. Frappe gives a user both on a File they uploaded or on one attached to a document they may change. Sharing a File gives write permission, enough for the file you keep, but never delete permission. The System Manager role alone gives neither, and Administrator always has both.
- The files must all be private or all be public, and stored in the same place: on the site, in cloud storage, or at the same kind of external address.

> [!WARNING]
> A merge cannot be undone. The merged File records are deleted and their content is removed. Try it on a copy of the site first, and take a backup of the database and the files.

## Merge files in the File Manager

1. Open the **File** list. Frappe shows it as the **File Manager**, in its list or grid view, or as a report view.
2. Tick two or more files: the duplicates and the one you want to keep. Folders cannot be merged.
3. Open the **Actions** menu and click **Merge Files**.
4. In **File to Keep**, choose the file to keep among the ones you ticked, and click **Merge**.
5. Read the warning and click **Merge** again.

## Merge a file from its form

1. Open the duplicate file.
2. Click **Actions → Merge into...**.
3. In **File to Keep**, pick the file to keep. The list offers files, not folders, with the same privacy as this one.
4. Click **Merge**, read the warning and click **Merge** again. The form of the file you kept opens.

## The merge log

When the merge is done, a **File Merge Log** shows one line per merged file: how many references were changed and what happened to the file, or, in red, why it was not merged. Each file is merged on its own: a file that is refused, for example for lack of permission, is left as it was, and the others are still merged. The ticks are cleared and the list refreshes.

## What a merge does

For each merged file:

- every Attach and Attach Image field that holds its URL, in every DocType, child tables and Single DocTypes included, gets the kept file's URL;
- every Text Editor, HTML Editor, Markdown Editor, Long Text and Code field that contains its URL gets the kept file's URL in its place. The URL is replaced where it stands on its own, relative or with the site's address, percent-encoded or HTML-escaped: `/files/logo.png.bak` or `/files/logo.png-2` is left alone. A private file's `?fid=` is kept when the merged File stays (below) and dropped when it is deleted. Spaces, quotes, `<`, `>` and backticks in the kept file's URL are written percent-encoded in these fields, so that the URL cannot end an HTML attribute or a Markdown link early;
- when the merged File record is deleted, every Link field that names it, and every comment, share and version that belongs to it, moves to the kept file, as in Frappe's own merge;
- other File records that share its content, the attachment copies Frappe makes, take the kept file's content. Only a record with exactly the same URL counts: `/files/Logo.png` is another file than `/files/logo.png`, although the database compares them without regard to case;
- a comment on the kept file records what was merged into it and how many references were changed.

These are written straight to the database, without saving each document, so they also change submitted and cancelled documents, and the documents' **Last Updated On** does not change. The records of the past are left alone: **Version** and **Deleted Document**. After the merge is saved, the caches Frappe builds from those documents are cleared: each user's desk loads afresh (with the app logo, for example) and the website's cached pages are rebuilt.

The kept file keeps its own name, content and settings.

### Attachments

A merged file that is attached to a document stays on that document, now as an attachment of the kept file: its File record stays, with the kept file's URL and content. When the document already has the kept file attached, or no longer exists, the merged File record is deleted instead. A merged file attached to nothing is deleted.

### The content

The merged file's content is removed after the merge is saved, and only when no File record uses it any more. When the merged file and the kept file are copies of the same upload, which Frappe stores once and both use, the content stays. Its thumbnail is removed the same way. A file stored in a sub-folder of the site's files, or at an external address, is never removed.

## With the cloud storage app

On a site with the [cloud_storage](https://github.com/agritheory/cloud_storage) app installed, files can be kept in an S3 bucket, and one File record stands for every document its content is attached to: the **File Association** rows of the File record list the documents. Data Steward does not depend on the app; it notices it on the site and merges the way the app expects.

- The merged file's File Association rows move to the kept file, except for a document the kept file is already attached to. A merged file attached from before the app was installed, with no row, gets one. If the kept file was attached to nothing, it is now attached to the first of those documents, as the app's own uploads are. The documents then list the kept file as their attachment, and the merged File record is always deleted.
- References to the merged file's `/api/method/retrieve?key=<KEY>` URL are rewritten like any other URL, also when the key itself is percent-encoded.
- The merged file's **sharing link** moves to the kept file when the kept file has none, so links already sent out keep working and now share the kept file. When both have one, the merged file's link stops working; links to it on the site are changed to the kept file's, and the merge log says so.
- The merged file's **versions** are not carried over, and the log says how many there were.
- Other File records that share the merged file's content, by URL or by S3 key, are merged into the kept file too, the same way, and the log says how many. The app's delete removes the content a File record names even when another record uses it, so a record left sharing the kept file's content could later remove it.
- The merged file's object in the bucket is deleted after the merge is saved, through the app's own S3 client, and only when no File record names its key any more, in its URL or its S3 key. The app's own delete would remove the object whatever else uses it, so it is never left to act on the merged File record. In a bucket with versioning, deleting an object keeps its earlier versions, as it does when the app deletes a file.
- The kept file's object is looked up in the bucket before anything is merged.

A file in the bucket and a file on the site cannot be merged into each other, and neither can be merged while the site's cloud storage is not configured.

## What is refused

The whole merge is refused, with nothing changed, when:

- **Allow File Merge** is off, or you do not have the System Manager role;
- the file to keep does not exist, is a folder, has no URL, or you lack write permission on it;
- the content of the file to keep is missing on the site or in the bucket;
- you send more than 100 files, or none.

A single file is refused, with a red line in the log, when it is the file to keep, does not exist, is a folder, is private while the kept file is public or the other way around, is stored somewhere else, or you lack delete permission on it.

## Limits

- Only the field types listed above are searched. A URL in a Data, Small Text or Text field, or in a file's own content, is not changed.
- A URL written with a different site address, such as an old domain, is not changed.
- Each merge searches every Attach and text field of the site, so on a large site a merge of many files takes a while. Merge in batches.
- The merged files' own names and settings are not copied to the kept file.
- A **Website Theme** whose custom SCSS used the merged file's URL is changed, but its compiled style sheet is not rebuilt. The log names the theme: open it and save it to rebuild the style sheet.

## Related

- [Merge duplicate records](merge-records.md)
- [Configuration](configuration.md)
- [Limitations and troubleshooting](troubleshooting.md)
