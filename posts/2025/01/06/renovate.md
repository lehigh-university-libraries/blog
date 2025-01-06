---
title: "Automating dependency updates in Islandora's Docker images using Renovate"
date: "2025-01-06"
author: "Joe Corall"
tags: ["islandora", "docker", "appsec", "mend.io", "renovate", "github-actions"]
---

We recently collaborated with [the Islandora Community](https://islandora.ca) to enhance the security posture of the Docker images provided by the Islandora Open Source project [Islandora-Devops/isle-buildkit](https://github.com/islandora-devops/isle-buildkit) utilizing [Mend's Renovate CLI](https://www.mend.io/renovate/) to keep dependencies up to date. Here at Lehigh we run the community-supported Docker images in our own digital repository [The Lehigh Preserve](https://preserve.lehigh.edu). Adding this integration has been a win-win: the community repository benefits from automated updates, ensuring all institutions using these images stay up-to-date, and, in turn, our instance remains up-to-date as well.

## Background

Over the 2024 winter holiday I happened to come across a CVE advisory (that was several weeks old) for a piece of software I knew handled web traffic for some of our services running in our Islandora stack. In this particular case I knew the service was only accessible from `localhost` so the threat was minor, but it had me concerned what other CVEs might be out there undetected. And going forward how quickly we will find/patch new CVEs for dependencies in our software.

This general problem had been top of mind, as I had recently been integrating [Mend's Renovate](https://www.mend.io/renovate/) with some of our local repositories here at Lehigh. This endevaor was initiated by reading some glowing reviews for the renovate bot in [hangops slack](https://github.com/hangops) and more recently hearing about some successes shared in [CODE4LIB's #devops slack channel](https://code4lib.org/irc/).

From [Mend's datasheet for Renovate](https://www.mend.io/wp-content/uploads/2023/09/Mend-Renovate-Enterprise-data-sheet.pdf) the problem renovate aims to solve is

> Keeping your dependencies up to date is one of the easiest ways to reduce technical debt and improve software security.  However, manually tracking and updating dependencies can be incredibly tedious and timeconsuming. As applications scale, the need for continuous maintenance, combined with the growing number of dependencies in use, can introduce fragility challenges for organizations, particularly as outdated components pile up technical debt.

Mend offers [an open source CLI](https://github.com/renovatebot/renovate) that:

> helps to update dependencies in your code without needing to do it manually. When Renovate runs on your repo, it looks for references to dependencies (both public and private) and, if there are newer versions available, Renovate can create pull requests to update your versions automatically.

## Getting started

To start, I issued a PR with a basic `renovate.json` file in the [Islandora-Devops/isle-buildkit] repository with some initial dependencies specified using [advanced capture](https://docs.renovatebot.com/modules/manager/regex/#advanced-capture). In the PR I also linked to an example PR renovate created in a fork of the repo to help demonstrate the value renovate add for us.

I created the initial PR by running the renovate CLI on my local machine. Mend offers a free GitHub app that can run the renovate CLI for your repos automatically with a simple install of their app in your GitHub organization. Though while [reading the renovate docs](https://docs.renovatebot.com/) realized we need to utilize renovate's [postUpgradeTasks](https://docs.renovatebot.com/configuration-options/#postupgradetasks), which is only available on self-hosted runners.

The reason we needed a postUpgradeTask is due to Islandora's dockerfiles not only pin the version of a given piece of software (something renovate handles very well), but the dockerfiles also hardcode the SHA256 of the binary being installed. Since renovate does not natively support the ability to extract a sha256 from a file, we needed a custom shell script to also update the SHA. It's a fairly straightforward process of just calculating the SHA and updating the dockerfile accordingly

```bash

#!/usr/bin/env bash

set -eou pipefail

DEP=$1
OLD_VERSION=$2
NEW_VERSION=$3
NEW_DIGEST=$4
URL=""
ARG=""
DOCKERFILES=()
README=""

echo "Updating SHA for $DEP@$NEW_VERSION"

if [ "$DEP" = "apache-tomcat" ]; then
  URL="https://downloads.apache.org/tomcat/tomcat-9/v$NEW_VERSION/bin/apache-tomcat-$NEW_VERSION.tar.gz"
  ARG="TOMCAT_FILE_SHA256"
  DOCKERFILES=("tomcat/Dockerfile")
  README="tomcat/README.md"

elif [ "$DEP" = "apache-activemq" ]; then
  URL="https://downloads.apache.org/activemq/$NEW_VERSION/apache-activemq-$NEW_VERSION-bin.tar.gz"
  ARG="ACTIVEMQ_FILE_SHA256"
  DOCKERFILES=("activemq/Dockerfile")
  README="activemq/README.md"
elif [ "$DEP" = "apache-log4j" ]; then
  URL="https://archive.apache.org/dist/logging/log4j/${NEW_VERSION}/apache-log4j-${NEW_VERSION}-bin.zip"
  ARG="LOG4J_FILE_SHA256"
  DOCKERFILES=(
    "blazegraph/Dockerfile"
    "fits/Dockerfile"
  )
# elif ...
# elif ...
# elif ...
else
  echo "DEP not found"
  exit 0
fi

SHA=$(curl -Ls "$URL" | shasum -a 256 | awk '{print $1}')
if [[ "$OSTYPE" == "darwin"* ]]; then
  sed -i '' 's|^ARG '"$ARG"'=.*|ARG '"$ARG"'="'"$SHA"'"|g' "${DOCKERFILES[@]}"
else
  sed -i 's|^ARG '"$ARG"'=.*|ARG '"$ARG"'="'"$SHA"'"|g' "${DOCKERFILES[@]}"
fi

# update the README to specify the new version
if [ "$README" != "" ]; then
  if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/${OLD_VERSION}\.$/${NEW_VERSION}\./" "$README"
  else
    sed -i "s/${OLD_VERSION}\.$/${NEW_VERSION}\./" "$README"
  fi
fi
```

Since we also list the version of a binary in a README, we update that value, too, while we're at it.

The PR was reviewed and merged! Then after running the CLI locally [our first renovate PR was created and merged](https://github.com/Islandora-Devops/isle-buildkit/pull/364)!

### Moving to GitHub Actions

Running locally was fine to get us started, but to complete the dream of detecting CVEs soon after they're published, getting this to run on a schedule is a must.

Renovate [needs a GitHub token so the CLI can auth to GitHub with privileges to create PRs/issues/commits with the necessary updates in the given repo](https://docs.renovatebot.com/modules/platform/github/#running-using-a-fine-grained-token). One could create a bot account + PAT to handle this (or maybe even a personal, scoped PAT), but instead opted to create a GitHub app in our GitHub org. The GitHub App is needed to generate a scoped GitHub access token to allow renovate to create PRs for us in the GitHub Action workflow. Then we can create a pretty simple GHA to have updates detected and PRs issued:


```yaml
name: run renovate

on:
  workflow_dispatch:
  # Monday mornings
  schedule:
    - cron: '15 1 * * 1'

env:
  LOG_LEVEL: debug
  RENOVATE_REPOSITORIES: islandora-devops/isle-buildkit
  RENOVATE_ALLOWED_POST_UPGRADE_COMMANDS: '["bash ci/update-sha.sh \"{{{depName}}}\" \"{{{currentVersion}}}\" \"{{{newVersion}}}\" \"{{{newDigest}}}\""]'
jobs:
  run:
    runs-on: ubuntu-24.04
    timeout-minutes: 10

    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4

      - uses: actions/setup-node@39370e3970a6d050c480ffad4ff0ed4d3fdee5af # v4
        with:
          node-version: 20

      - name: run renovate
        run: |
          # fetch GitHub App token for this repo
          echo "${{ secrets.GH_APP_PRIV_KEY }}" | base64 -d > private-key.pem
          export RENOVATE_TOKEN=$(./ci/fetch-app-token.sh ${{ secrets.GH_APP_ID }} ${{ secrets.GH_APP_INSTALLATION_ID }} private-key.pem)

          # run renovate with our token
          npx renovate --platform=github
```

## Future work

There are a few more dependencies in the repo I'd like to cover in the targeted repo. And we could possibly pin `apk` packages in our Dockerfiles since we can now automate bumping those versions.

[Islandora-Devops/isle-buildkit]: https://github.com/Islandora-Devops/isle-buildkit
