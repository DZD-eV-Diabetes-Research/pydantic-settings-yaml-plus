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


### ToDo / ToInvestigate
* What about date(times) support?
* Refactor / Remove dead code psyplus.YamlSettings
* Make env vars work!
* Remove debug prints
* Write some basic tests
* Make pypi package

### Known Issues
* Multiline values are crippled
* datetime.time is not supported as yaml.load interpretes it as a tuple
* Nested lists are making some weird stuff: No env var can be generated, InfoHeader is missing on first item
* Dicts

# Why does this have a kind of custom yaml parser

At the moment the Python default YAML library has no support for comments.
https://github.com/yaml/pyyaml/issues/90
There is an alternative package called https://pypi.org/project/ruamel.yaml/ that seems to support yaml.
But we are working here with reasonable simple yaml structures (Pydantic object exports) therefor it seems reasonable for me to write a simple parser on my own.
This way we save a third party dependency, which tend to brake things from time to time. Also ruamel.yaml seems to be carried by only one person.
And i was curious if its feasable :) 
In future when https://github.com/yaml/pyyaml/issues/90 may be resolved, i'll switch to a Python native variant of parsing/inceting yaml comments.