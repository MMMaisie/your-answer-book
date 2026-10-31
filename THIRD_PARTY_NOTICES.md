# References and third-party material

The implementation retains the project's own chart and reading code. Design review drew on:

- https://github.com/1eakkkk/liuyao-tool (reviewed commit 105e75748617beab0cac693b1e91029e41e08d1a): evidence/prose separation, optional reference validation, snapshot design.
- https://github.com/Johnson-Jia/liuyao-divination (1a5a78b513c0e7b46dfb29f74043bcf978c32a3e): structured chart fields and independent basic-chart comparison. Its unconditional effectiveness rules were not imported.
- https://github.com/gundamdarke398-ship-it/liuyao-divination (e27b95a7defb3311540845fa364d96997e80d8b9): explicit golden-case test structure and offline export concept. Its browser API-key flow and specific-date prompts were not imported.

Their code is not vendored into the running website; the review does not certify their predictive accuracy or their classical-source transcription.

Noto Sans SC (regular-weight instance of Google's font distribution) is bundled in fonts for PDF embedding. See fonts/OFL.txt for its SIL Open Font License and attribution. Distribution source: https://github.com/google/fonts/tree/main/ofl/notosanssc .

Book reference data is the project's existing paraphrase/case archive, not a newly trained model. Original editorial editions and commentary may carry separate rights; this package does not include the uploaded PDFs.
