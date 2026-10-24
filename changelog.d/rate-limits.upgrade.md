Caddy now sends each visitor's address to the site, which the new limits count by. After
deploying, run `sudo docker compose exec -w /etc/caddy caddy caddy reload` in `deploy/aws/`:
`up -d` keeps Caddy on its old configuration, and until it's reloaded every visitor counts as one
([#226](https://github.com/dipbazz/Charity-wagtail-CMS/issues/226)).
