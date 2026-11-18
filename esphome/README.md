# ESPHome firmware

For a new Solesta installation, use the
[public NanoC6 firmware kit](public/README.md). It contains the current
source configuration, a secrets template, wiring instructions and setup
steps for the Solesta debug header. Each user creates a private `secrets.yaml`
in their own ESPHome configuration directory.

`solesta-nanoc6-demo.yaml` is an earlier research snapshot kept for historical
reference. It is not the public installation entry point. Both configurations
receive serial data on GPIO1 at 57600 8N1; neither drives the Solesta header.
