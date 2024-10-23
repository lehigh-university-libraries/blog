# Lehigh University Library Technology Blog

Blog entries are created in the [posts](./posts) directory as markdown files. Each blog post is put into a directory named after the year/month/day it was created.

## Testing locally

If instead of using a PR to test your changes, you also can run the site locally.

```
git clone git@github.com:lehigh-university-libraries/blog.git
cd blog
# replace with actual year/month/day
mkdir -p YYYY/MM/DD
vi YYYY/MM/DD/filename.md
# populate blog contents
docker run -d --name ltblog -it --rm -p 8000:8000 -v $(pwd):/app ltblog:latest
docker exec ltblog python build
```

Visit [http://localhost:8000](http://localhost:8000) in your web browser to view your new entry.

You can make edits to you post and run `docker exec ltblog python build` again to see the changes.
