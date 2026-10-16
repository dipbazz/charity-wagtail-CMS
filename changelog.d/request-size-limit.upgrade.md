Caddy now refuses any request over 12 MB, so nobody can fill the server's disk with one upload.
After deploying, run `sudo docker compose exec -w /etc/caddy caddy caddy reload` in
`deploy/aws/`: `up -d` keeps Caddy on its old configuration. The nightly backup now deletes old
receipt screenshots after it has copied the backup to S3
([#217](https://github.com/dipbazz/Charity-wagtail-CMS/pull/217)).
