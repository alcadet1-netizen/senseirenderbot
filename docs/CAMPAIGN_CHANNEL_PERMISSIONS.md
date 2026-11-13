# Campaign startup: channel publishing permission

The production traceback `Bot needs channel post permission` is raised before
polling starts. It prevents every command, including `/upkatana`, from being
handled; it is not evidence of a GIF rendering failure.

Campaigns observe posts in the channel and publish announcements/results only
in the linked discussion supergroup. Requiring `can_post_messages` in the
channel was unnecessary. Initialization now permits an administrator without
that publishing flag. Administrator membership in both chats, linked-discussion
validation, Mongo transaction checks, indexes and durable inbox admission are
unchanged. Other initialization failures still prevent polling: do not simply
catch all startup exceptions or skip durable ingress.

Operational workaround for the old build: grant the bot channel administrator
permission to publish posts. With the fix, this additional privilege is not
needed. The bot must still be administrator in the configured channel and linked
discussion. No database reset or backlog deletion is required.

Regression tests cover false/absent/true publish flags and reject non-admin
membership in either chat. These use a fake Mongo harness; deployment, actual
Telegram rights and live command delivery need separate verification.
