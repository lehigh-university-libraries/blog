---
title: "Upgrading our IIIF server: rolling out triplet at Lehigh"
date: "2026-04-29"
author: "Joe Corall"
tags: ["islandora", "drupal", "docker", "iiif", "vips"]
---

As Lehigh University Libraries' digital repository, [The Lehigh Preserve](https://preserve.lehigh.edu), continues to expand - especially with image-intensive collections that rely on [IIIF](https://iiif.io/) for web display - the performance of our IIIF server has become critical to our daily operations. We frequently encounter server load spikes driven by a combination of aggressive bot traffic and standard site visitor interactions with large TIFF files.

Islandora ships with [Cantaloupe](https://cantaloupe-project.github.io/) as its default IIIF server, which has served us exceptionally well since the launch of our modern stack in June 2024. However, as our operational demands have scaled, we have begun exploring new strategies to optimize and enhance server performance.

## triplet

[triplet](https://github.com/libops/triplet) is a new IIIF server written in Go that relies on [libvips](https://github.com/libvips/libvips) for all image processing. Both architectural choices are significant: Go delivers a small, fast, statically compiled binary with robust concurrency, while libvips stands out as one of the fastest image processing libraries available.

## Benchmarks against Cantaloupe

Before exposing triplet to production traffic, we conducted an apples-to-apples benchmark against our current Cantaloupe solution. While the [full results are available in the triplet repository](https://github.com/libops/triplet#benchmark-against-cantaloupe), the primary takeaway is that triplet outperforms Cantaloupe across virtually every metric we prioritize:

- **Uncached latency:** `1.6–3.7×` faster median, and `4–5×` faster at the p99 tail across all tested concurrency levels.
- **Cached latency:** `1.3–2.1×` faster across every request type.
- **JP2 support:** 100% success rate, operating `2.4–5.7×` faster uncached.
- **Concurrency scaling:** Latency increased by only `5×` when scaling from `1` to `8` concurrent clients, compared to `11.3×` for Cantaloupe.
- **CPU efficiency:** Requires `3–3.5×` less CPU per uncached request, and roughly `6×` less when cached.
- **Memory footprint:** `6–11×` lower uncached, and `2–3×` lower cached.

The only area where Cantaloupe retains an edge is in the output size of full-resolution JPEGs derived from large TIFFs, where triplet's output is roughly 1.36× larger. Given the significant performance gains elsewhere, this is a tradeoff we are more than willing to accept.

## An unmeasured performance improvement: filesystem-aware source resolution

One standout, Islandora-specific feature in triplet is its ability to read directly from Drupal or Fedora ([OCFL](https://ocfl.io/)) filesystems, which are mounted into the IIIF container as read-only volumes. The IIIF specification allows clients to pass a full URL as the image identifier, making requests like the following perfectly standard:

```
https://preserve.lehigh.edu/iiif/3/https%3A%2F%2Fpreserve.lehigh.edu%2Fsystem%2Ffiles%2Fderivatives%2Fservice%2Fnode%2F9375%2F9375-service-file.tiff/info.json
```

Typically, a IIIF server treats this identifier as a remote URL and fetches it over HTTP. While functional, this is inefficient when triplet and Drupal share the same hardware and disk access. More critically, it places the Drupal stack in the critical path of every uncached IIIF request, forcing it to serve potentially multi-gigabyte TIFFs to the IIIF server before image processing can even begin. 

Triplet’s URL mapping feature solves this by recognizing when a path like `/system/files/derivatives/service/node/9375/9375-service-file.tiff` exists on a locally mounted volume, allowing it to read the file straight from disk (falling back to HTTP streaming if necessary). This removes Drupal from the file transfer process entirely, freeing up PHP workers to handle the requests they are actually meant for.

The relevant configuration block looks like this:

```yaml
sources:
  default: file
  file:
    root: /public
    url_mappings:
      - prefix: /sites/default/files
        root: /public

      - prefix: /system/files
        root: /private
        auth_probe: true

      - prefix: /_flysystem/fedora
        root: /fcrepo
        ocfl: true
        auth_probe: true
  http:
    allowed_origins:
      - https://preserve.lehigh.edu
    allow_private_hosts: true
    metadata_cache_ttl: 240h
```

### Permitting Access to Protected IIIF Assets

Another critical feature worth highlighting is `auth_probe`. Reading files directly from the disk could easily introduce an authorization bypass if we aren't careful to verify permissions. When `auth_probe` is enabled, triplet addresses this by first asking the original Drupal URL if the request is authorized—checking anonymously first, and then with the user's cookie if needed—before it serves the local file. To prevent these checks from becoming a new bottleneck, anonymous and authenticated probe results are cached separately with distinct TTLs. Because this probe is just a lightweight `HEAD` request, Drupal does drastically less work than it would under the default "fetch-the-whole-file" behavior.

There is a theoretical cache-poisoning risk here (specifically, if permissions change on the underlying source before the cache expires). We intend to address this with targeted invalidation requests as we scale this pattern out. Given Lehigh's current threat model and traffic shape, however, it isn't an immediate concern. We are moving forward with this approach now and will layer in invalidation in the coming weeks.

### Restricting Allowed HTTP Sources

We have also secured the HTTP fallback path using an allowlist. Because IIIF identifiers can be full URLs, an unconfigured IIIF server can inadvertently act as an open proxy. While that is useful for legitimate cross-repository requests, it becomes a severe liability if a bad actor points it at an internal or unrelated host. Triplet's `sources.http.allowed_hosts` setting restricts the domains it can fetch images from to our own trusted repository hostnames. Even if a request falls through to HTTP streaming, triplet will only ever pull bytes from approved sources.

## A Related Win: Pyramidal Tiled TIFF Service Derivatives

While deep in this infrastructure work, we identified another major optimization: transitioning our service-file derivatives from JP2s to Pyramidal Tiled TIFFs (PTIFs). 

Making this switch yields significant storage and performance improvements. Here are two examples from our collection that highlight the difference:

- A **3.83 GiB source TIFF** originally produced a 1 GiB JP2 service file. Reprocessing it as a Pyramidal Tiled TIFF reduced it to **389 MiB**.
- A **1 GiB source TIFF** originally produced a 411 MiB JP2 service file. Reprocessing it as a Pyramidal Tiled TIFF reduced it to **98 MiB**.

The pyramidal tiled format also aligns perfectly with how IIIF servers actually read images. Instead of walking the entire codestream, the server can efficiently decode only the specific tiles and resolution levels it needs to satisfy a request. Combined with triplet's libvips pipeline, this delivers a substantial serving-time performance boost on top of the storage savings. We will be rolling this out as a follow-up improvement.

Here is how we are updating our JP2 service files (invoked with `drush scr`):

```php
<?php

// helper to login as an auth'd account
lehigh_islandora_cron_account_switcher();

$action_name = 'generate_a_jp2_service_file';
$entity_type_manager = \Drupal::entityTypeManager();
$node_storage   = $entity_type_manager->getStorage('node');
$media_storage   = $entity_type_manager->getStorage('media');
$action_storage = $entity_type_manager->getStorage('action');
$action = $action_storage->load($action_name);

$sql = "SELECT f.entity_id, field_media_of_target_id
  FROM media__field_media_file f
  INNER JOIN media__field_media_of mo ON mo.entity_id = f.entity_id
  INNER JOIN media__field_media_use mu ON mu.entity_id = f.entity_id
  INNER JOIN file_managed fi ON fid = field_media_file_target_id
  WHERE field_media_use_target_id = :stid
    AND fi.uri LIKE '%.jp2'
    AND f.entity_id NOT IN (
      SELECT entity_id
        FROM media__field_media_use
        WHERE field_media_use_target_id = :otid
      )";
$d_args = [
  ':stid' => lehigh_islandora_get_tid_by_name("Service File", "islandora_media_use"),
  ':otid' => lehigh_islandora_get_tid_by_name("Original File", "islandora_media_use"),
];
$results = \Drupal::database()->query($sql, $d_args)->fetchAllKeyed();

foreach ($results as $mid => $nid) {
  $media = $media_storage->load($mid);
  if (!$media) {
    continue;
  }
  $file = $media->field_media_file->entity;
  $media->delete();
  if ($file) {
    $file->delete();
  }

  $node = $node_storage->load($nid);
  if (!$node) {
    continue;
  }

  $action->execute([$node]);
}
```

## Rollout plan

We rolled out triplet this week, and we're going to slow-roll traffic to it while monitoring performance. We're able to gradually send traffic from cantaloupe to triplet because we have a custom Drupal module that caches our IIIF manifests. So we can use random cache invalidation paired with normal web traffic patterns to slowly move everything to triplet while we monitor

```bash
FILES=$(sudo find "/path/to/manifest" -name book-manifest.json -mtime +1)
COUNT=$(echo "$FILES" | wc -l)
# move 5% of traffic over to triplet
DELETE=$(( COUNT * 5 / 100 ))

echo "$FILES" | shuf | head -n "$DELETE" | while read -r file; do
    node_id=$(echo "$file" | grep -oP 'node/\K[0-9]+')
    echo "Deleting $file"
    sudo rm "$file"
    echo "Warming node/${node_id}"
    curl -s -o /dev/null "https://preserve.lehigh.edu/node/${node_id}/book-manifest"
done
```

If we see anything unexpected (performance regressions, edge-case rendering bugs, manifests that don't behave the way we expect) we can flip the manifest routes back to Cantaloupe. That safety net is a big part of why we're comfortable moving forward this week rather than waiting on a longer staging cycle.
