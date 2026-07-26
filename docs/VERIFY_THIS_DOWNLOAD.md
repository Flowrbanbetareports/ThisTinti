# Verify this ThisTinti download

Do not use a file name, an embedded version string or an old build record as
proof that a Windows download is the published candidate.

For a Public Preview artifact:

1. download the `.exe` or `.zip` together with its same-name `.sha256` file;
2. calculate the file SHA-256 locally and require an exact match;
3. download `release-provenance.json` from the same GitHub Actions artifact or
   GitHub prerelease;
4. require the provenance inventory to contain that exact file name, byte size
   and SHA-256;
5. require its source commit, source tree, workflow run and artifact name to
   match the successful candidate workflow;
6. for the portable ZIP, open the root `BUILD-IDENTITY.json` and require the same
   source and workflow identity.

`BUILD-IDENTITY.json` is an assertion embedded before the portable archive is
hashed. It is useful for identifying a detached ZIP, but it is not a signature
and is not sufficient by itself. The detached checksum, provenance inventory and
GitHub workflow identity must agree.

The Windows executables are currently unsigned. Windows may therefore show an
unknown-publisher warning even when these integrity checks pass.
