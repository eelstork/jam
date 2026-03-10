# Fastr - fast and safe git repos

I get you, I get you. Therefore we have a specification for a reasoned create-repo command, and more generally a reasoned API.

First we need to step back from the file system. We are going to assume a target directory for all repos. So this needs to be set in, I guess... idk, an environment variable maybe?

```
new NAME "DESCRIPTION"
```

This is the action, right? It's going to check for "dev-home" in env and if does not exist, goodbye.
Then it's going to check whether repo with this name exists, and if not, goodbye.
Then it's going to create the repo via gh, create the readme from description (not optional. many operations fail with a content-less repo), and push, right?

Then we have a key action that's much easier than github template repos

```
clone NAME as NAME "RE-DESCRIPTION"
```

I think it's obvious what this does, correct?
```
list => i believe we will need this.
```
merge-pull => this is an operation that can help quickly pulling from a fresh branch and merging code changes
```
up NAME "commit-comment"
```
add all, commit with message, push

```
down
```

I see. So this is the boogie, right?
