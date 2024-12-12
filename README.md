# omeka2dsp

This project contains the data model for the long-term preservation of the research data of [Stadt.Geschichte.Basel (SGB)](https://stadtgeschichtebasel.ch/) on the [DaSCH Service Platform (DSP)](https://www.dasch.swiss/plattform-characteristics) and the necessary scripts to transfer the research data from omeka to the DSP.

The script transfers the metadata and the associated media files from the SGB Omeka instance to the DSP. If a data object with the same id already exists on the DSP, the metadata is updated according to the omeka instance if it has changed.

[![GitHub issues](https://img.shields.io/github/issues/koilebeit/omeka2dsp.svg)](https://github.com/koilebeit/omeka2dsp/issues)
[![GitHub forks](https://img.shields.io/github/forks/koilebeit/omeka2dsp.svg)](https://github.com/koilebeit/omeka2dsp/network)
[![GitHub stars](https://img.shields.io/github/stars/koilebeit/omeka2dsp.svg)](https://github.com/koilebeit/omeka2dsp/stargazers)
[![GitHub license](https://img.shields.io/github/license/koilebeit/omeka2dsp.svg)](https://github.com/koilebeit/omeka2dsp/blob/main/LICENSE.md)

## Installation

Use the package manager [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm) to install all dependencies.

```bash
npm install
```

## Usage

### Preconditions

You need an already created project with the provided [data model](data/data_model_dasch.json) on a DSP instance. If this needs to be created, this can be done using the [DSP-Tools](https://docs.dasch.swiss/latest/DSP-TOOLS/) like this:

```
dsp-tools create -s 0.0.0.0:3333 -u root@example.com -p test data/data_model_dasch.json
```

(note: this requires system administrator rights on the DSP instance)

### Setting the environment variables

The following environment variables must be set:
|Environment variable | Description |
|---------------------|----------------|
|OMEKA_API_URL |URL of the Omeka API |
|KEY_IDENTITY |Your Omeka API identity |
|KEY_CREDENTIAL |Your Omeka API credential |
|ITEM_SET_ID |The itemset id of your Omeka collection |
|PROJECT_SHORT_CODE |Shortcode of your DSP project |
|API_HOST |URL of the DSP API |
|INGEST_HOST |URL of the DaSCH ingest host |
|DSP_USER |Your DSP username |
|DSP_PWD |Your DSP password |
|PREFIX |Prefix of your ontology (Default: StadtGeschichteBasel_v1) |

### Run the script

```
python scripts/data_2_dasch.py [-m]
```

- `-m all_data` process all data of the omeka instance (same as without -m)

- `-m sample_data` process a random selection of data from omeka

- `-m test_data`process only selected data of the omeka instance

### Configuration

You can configure the number of random data and specify the test data by adjusting the following variables in the [script](scripts/data_2_dasch.py):

```python
NUMBER_RANDOM_OBJECTS = 2
TEST_DATA = {'abb13025', 'abb14375', 'abb41033', 'abb11536', 'abb28998'}
```

## Support

This project is maintained by [@koilebeit](https://github.com/koilebeit). Please understand that we won't be able to provide individual support via email. We also believe that help is much more valuable if it's shared publicly, so that more people can benefit from it.

| Type                                   | Platforms                                                                |
| -------------------------------------- | ------------------------------------------------------------------------ |
| 🚨 **Bug Reports**                     | [GitHub Issue Tracker](https://github.com/koilebeit/omeka2dsp/issues)    |
| 📚 **Docs Issue**                      | [GitHub Issue Tracker](https://github.com/koilebeit/omeka2dsp/issues)    |
| 🎁 **Feature Requests**                | [GitHub Issue Tracker](https://github.com/koilebeit/omeka2dsp/issues)    |
| 🛡 **Report a security vulnerability** | See [SECURITY.md](SECURITY.md)                                           |
| 💬 **General Questions**               | [GitHub Discussions](https://github.com/koilebeit/omeka2dsp/discussions) |

## Roadmap

No changes are currently planned.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/koilebeit/omeka2dsp/tags).

## Authors and acknowledgment

- **Nico Görlich** - _Initial work_ - [koilebeit](https://github.com/koilebeit)

See also the list of [contributors](https://github.com/koilebeit/omeka2dsp/graphs/contributors) who participated in this project.

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details.
