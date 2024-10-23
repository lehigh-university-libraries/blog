# Lehigh University Library Technology Blog

Blog entries are created in the [posts](./posts) directory as markdown files. Each blog post is put into a directory named after the year/month/day it was created.

## Testing locally

You can run the site locally.

```
git clone git@github.com:lehigh-university-libraries/blog.git
cd blog
# replace with actual year/month/day
mkdir -p YYYY/MM/DD
vi YYYY/MM/DD/filename.md
# populate blog contents

# run the server
docker run -d --name ltblog -it --rm -p 8000:8000 -v $(pwd):/app ltblog:latest
# generate the static site
docker exec ltblog python build
```

Now you can visit [http://localhost:8000](http://localhost:8000) in your web browser to view your new blog post.

You can make edits to you post and run `docker exec ltblog python build` again to see the changes.
