CRWIZ: A framework for collecting real-time Wizard of Oz dialogues through Crowdsourcing for collaborative, complex tasks
==============================================================================

To appear at LREC 2020, see [Publication] for more information. The data collected is in the compressed file "data_collected.zip".


### Running CRWIZ

Python version: >= 3.7.0

Known working versions: Python 3.7.2 and Python 3.7.6

- Create virtual environment

      $ python3.7 -m venv .venv-crwiz

- Install requirements from requirements.txt:

      $ pip install -r requirements.txt

- Run the CRWIZ framework:

      $ python run.py

- Go to [localhost:5000/portal] in two different browsers to be paired up.


There is a docker-compose file to easily deploy on a server.


Check [Slurk] for more information, particularly for how to deploy it or how the bots work (e.g. for the pairing up of participants).


## Publication

Please cite our work as the following:

    Chiyah Garcia, F., Lopes, J., Liu, X., and Hastie, H. 2020. CRWIZ: A Framework for Crowdsourcing Real-Time Wizard-of-Oz Dialogues. In Proceedings of the Twelfth International Conference on Language Resources and Evaluation (LREC 2020). European Language Resources Association (ELRA).

Bibtex:

```bibtex
@inproceedings{ChiyahLREC20,
    title = {CRWIZ: A Framework for Crowdsourcing Real-Time Wizard-of-Oz Dialogues},
    author = {Chiyah Garcia, Francisco J. and Lopes, Jos{\'{e}} and Liu, Xingkun and Hastie, Helen},
    booktitle = {Proceedings of the Twelfth International Conference on Language Resources and Evaluation (LREC 2020)},
    series = {LREC'20},
    year = {2020},
    month = {5},
    address = {Marseille, France},
    publisher = {European Language Resources Association (ELRA)},
}

```

## Other

Please, get in touch if you have any questions.

[https://jchiyah.github.io]


[Slurk]: https://clp-research.github.io/slurk/slurk_about.html#slurk-about
[localhost:5000/portal]: http://localhost:5000/portal
[publication]: #Publication
[https://jchiyah.github.io]: https://jchiyah.github.io
