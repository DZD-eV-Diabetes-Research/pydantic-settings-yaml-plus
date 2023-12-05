# pydantic-settings-yaml-plus
A tiny helper class to use pydantic-settings to generate, read and comment your config file in yaml
 work in progress. please ignore this repo for now


 ## Goals

* Have a single source of truth for config and all it meta data (type, descpription, examples)
* All values are overwritable by env var
* Generate template (minimal with required values only or maximum with all values listed) and example config files (all YAML only!)
  
### stretch goals
* generate diff betwen current config and config model (when config model changed after update)
* update existing config files metadata
  * Update info, descs
  * Add missing/new required values


### To investigate
* What about date(times) support?
* Support block values