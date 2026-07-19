#!/usr/bin/env python3
"""Internet Encyclopedia of Philosophy scraper.

Peer-reviewed articles covering major philosophical topics.
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class IEPScraper(BaseScraper):
    """Internet Encyclopedia of Philosophy scraper. Peer-reviewed articles covering major philosophical topics."""

    SOURCES = {
        "ethics": {
            "pages": {
                "https://iep.utm.edu/ethics/": "Ethics",
                "https://iep.utm.edu/virtue/": "Virtue Ethics",
                "https://iep.utm.edu/util-a-r/": "Act and Rule Utilitarianism",
                "https://iep.utm.edu/conseque/": "Consequentialism",
                "https://iep.utm.edu/deontolo/": "Deontological Ethics",
                "https://iep.utm.edu/care-eth/": "Care Ethics",
                "https://iep.utm.edu/nat-law/": "Natural Law",
                "https://iep.utm.edu/divine-c/": "Divine Command Theory",
                "https://iep.utm.edu/moral-re/": "Moral Realism",
                "https://iep.utm.edu/mor-anti/": "Moral Anti-Realism",
                "https://iep.utm.edu/moral-rl/": "Moral Relativism",
                "https://iep.utm.edu/moralpsyc/": "Moral Psychology",
                "https://iep.utm.edu/mor-reas/": "Moral Reasoning",
                "https://iep.utm.edu/moram-am/": "Moral Responsibility",
                "https://iep.utm.edu/autonomy/": "Autonomy",
                "https://iep.utm.edu/freewill/": "Free Will",
                "https://iep.utm.edu/hard-det/": "Hard Determinism",
                "https://iep.utm.edu/compatib/": "Compatibilism",
                "https://iep.utm.edu/doub-eff/": "Doctrine of Double Effect",
                "https://iep.utm.edu/egoism/": "Egoism",
                "https://iep.utm.edu/altruism/": "Altruism",
                "https://iep.utm.edu/bioethic/": "Bioethics",
                "https://iep.utm.edu/envi-eth/": "Environmental Ethics",
                "https://iep.utm.edu/ani-righ/": "Animal Rights",
                "https://iep.utm.edu/euthanasia/": "Euthanasia",
                "https://iep.utm.edu/abortion/": "Abortion",
                "https://iep.utm.edu/punishme/": "Punishment",
                "https://iep.utm.edu/justwar/": "Just War Theory",
                "https://iep.utm.edu/fem-eth/": "Feminist Ethics",
                "https://iep.utm.edu/non-cogn/": "Non-Cognitivism in Ethics",
                "https://iep.utm.edu/emotivism/": "Emotivism",
                "https://iep.utm.edu/prescr-m/": "Prescriptivism",
                "https://iep.utm.edu/moral-ep/": "Moral Epistemology",
                "https://iep.utm.edu/evil/": "The Problem of Evil",
                "https://iep.utm.edu/sen-cap/": "The Capability Approach",
                "https://iep.utm.edu/supერer/": "Supererogation",
                "https://iep.utm.edu/trust/": "Trust",
                "https://iep.utm.edu/well-bei/": "Well-Being",
                "https://iep.utm.edu/happiness/": "Happiness",
                "https://iep.utm.edu/hedonism/": "Hedonism",
                "https://iep.utm.edu/pleasure/": "Pleasure",
                "https://iep.utm.edu/inttic/": "Intrinsic and Extrinsic Properties",
                "https://iep.utm.edu/val-am/": "Value Theory",
                "https://iep.utm.edu/con-am/": "Consent",
                "https://iep.utm.edu/rights/": "Rights",
            },
        },
        "epistemology": {
            "pages": {
                "https://iep.utm.edu/epistemo/": "Epistemology",
                "https://iep.utm.edu/knowledg/": "Knowledge",
                "https://iep.utm.edu/gettier/": "Gettier Problems",
                "https://iep.utm.edu/justep/": "Epistemic Justification",
                "https://iep.utm.edu/found-am/": "Foundationalism",
                "https://iep.utm.edu/coherent/": "Coherentism",
                "https://iep.utm.edu/reliabil/": "Reliabilism",
                "https://iep.utm.edu/int-ext/": "Internalism and Externalism",
                "https://iep.utm.edu/skeptici/": "Skepticism",
                "https://iep.utm.edu/brainvat/": "Brain in a Vat",
                "https://iep.utm.edu/evil-dec/": "Evil Demon",
                "https://iep.utm.edu/a-priori/": "A Priori and A Posteriori",
                "https://iep.utm.edu/emp-ism/": "Empiricism",
                "https://iep.utm.edu/rational/": "Rationalism",
                "https://iep.utm.edu/induction/": "Induction",
                "https://iep.utm.edu/abductio/": "Abduction",
                "https://iep.utm.edu/evidence/": "Evidence",
                "https://iep.utm.edu/percepti/": "Perception",
                "https://iep.utm.edu/memory/": "Memory",
                "https://iep.utm.edu/testimon/": "Testimony",
                "https://iep.utm.edu/soc-epis/": "Social Epistemology",
                "https://iep.utm.edu/virt-epi/": "Virtue Epistemology",
                "https://iep.utm.edu/epis-nat/": "Naturalized Epistemology",
                "https://iep.utm.edu/contextu/": "Contextualism",
                "https://iep.utm.edu/ep-bayes/": "Bayesian Epistemology",
                "https://iep.utm.edu/fem-epis/": "Feminist Epistemology",
                "https://iep.utm.edu/self-kno/": "Self-Knowledge",
                "https://iep.utm.edu/oth-mind/": "Other Minds",
                "https://iep.utm.edu/truth/": "Truth",
                "https://iep.utm.edu/truth-co/": "Correspondence Theory of Truth",
                "https://iep.utm.edu/truth-ch/": "Coherence Theory of Truth",
                "https://iep.utm.edu/pragmati/": "Pragmatic Theory of Truth",
                "https://iep.utm.edu/deflationary/": "Deflationary Theory of Truth",
                "https://iep.utm.edu/ep-lucky/": "Epistemic Luck",
                "https://iep.utm.edu/closure/": "Epistemic Closure",
                "https://iep.utm.edu/ep-para/": "Epistemic Paradoxes",
                "https://iep.utm.edu/know-how/": "Knowledge-How",
                "https://iep.utm.edu/objectiv/": "Objectivity",
                "https://iep.utm.edu/rel-epis/": "Relativism",
                "https://iep.utm.edu/common-k/": "Common Knowledge",
            },
        },
        "metaphysics": {
            "pages": {
                "https://iep.utm.edu/metaphys/": "Metaphysics",
                "https://iep.utm.edu/substanc/": "Substance",
                "https://iep.utm.edu/properties/": "Properties",
                "https://iep.utm.edu/universa/": "Universals",
                "https://iep.utm.edu/tropes/": "Tropes",
                "https://iep.utm.edu/nat-kind/": "Natural Kinds",
                "https://iep.utm.edu/identity/": "Identity",
                "https://iep.utm.edu/person-i/": "Personal Identity",
                "https://iep.utm.edu/persistence/": "Persistence",
                "https://iep.utm.edu/time/": "Time",
                "https://iep.utm.edu/presentism/": "Presentism",
                "https://iep.utm.edu/etern-sm/": "Eternalism",
                "https://iep.utm.edu/spacetim/": "Space and Time",
                "https://iep.utm.edu/causatio/": "Causation",
                "https://iep.utm.edu/caus-met/": "Causation in Metaphysics",
                "https://iep.utm.edu/det-free/": "Determinism and Free Will",
                "https://iep.utm.edu/fatalism/": "Fatalism",
                "https://iep.utm.edu/poss-wor/": "Possible Worlds",
                "https://iep.utm.edu/modality/": "Modality",
                "https://iep.utm.edu/nec-cont/": "Necessity and Contingency",
                "https://iep.utm.edu/disposit/": "Dispositions",
                "https://iep.utm.edu/lawofnat/": "Laws of Nature",
                "https://iep.utm.edu/mereolog/": "Mereology",
                "https://iep.utm.edu/abstract/": "Abstract Objects",
                "https://iep.utm.edu/existenc/": "Existence",
                "https://iep.utm.edu/realism/": "Realism",
                "https://iep.utm.edu/nominali/": "Nominalism",
                "https://iep.utm.edu/material/": "Materialism",
                "https://iep.utm.edu/physicalism/": "Physicalism",
                "https://iep.utm.edu/dualism/": "Dualism",
                "https://iep.utm.edu/idealism/": "Idealism",
                "https://iep.utm.edu/monism/": "Monism",
                "https://iep.utm.edu/events/": "Events",
                "https://iep.utm.edu/facts/": "Facts",
                "https://iep.utm.edu/vague/": "Vagueness",
                "https://iep.utm.edu/composit/": "Composition",
                "https://iep.utm.edu/ontology/": "Ontology",
                "https://iep.utm.edu/category/": "Categories",
                "https://iep.utm.edu/truthmak/": "Truthmakers",
                "https://iep.utm.edu/ground/": "Grounding",
                "https://iep.utm.edu/superven/": "Supervenience",
                "https://iep.utm.edu/mult-rea/": "Multiple Realizability",
                "https://iep.utm.edu/emergenc/": "Emergence",
                "https://iep.utm.edu/change/": "Change",
                "https://iep.utm.edu/endurant/": "Endurantism and Perdurantism",
            },
        },
        "logic": {
            "pages": {
                "https://iep.utm.edu/logic-cl/": "Classical Logic",
                "https://iep.utm.edu/log-int/": "Intuitionistic Logic",
                "https://iep.utm.edu/modal-lo/": "Modal Logic",
                "https://iep.utm.edu/par-log/": "Paraconsistent Logic",
                "https://iep.utm.edu/fuzzy-lo/": "Fuzzy Logic",
                "https://iep.utm.edu/many-val/": "Many-Valued Logic",
                "https://iep.utm.edu/free-log/": "Free Logic",
                "https://iep.utm.edu/ded-ind/": "Deduction and Induction",
                "https://iep.utm.edu/val-snd/": "Validity and Soundness",
                "https://iep.utm.edu/fallacy/": "Fallacies",
                "https://iep.utm.edu/form-inf/": "Formal and Informal Logic",
                "https://iep.utm.edu/prop-log/": "Propositional Logic",
                "https://iep.utm.edu/pred-log/": "Predicate Logic",
                "https://iep.utm.edu/log-cond/": "Conditionals",
                "https://iep.utm.edu/log-cons/": "Logical Consequence",
                "https://iep.utm.edu/log-form/": "Logical Form",
                "https://iep.utm.edu/log-plur/": "Logical Pluralism",
                "https://iep.utm.edu/log-para/": "Logical Paradoxes",
                "https://iep.utm.edu/liar-par/": "The Liar Paradox",
                "https://iep.utm.edu/sorites/": "The Sorites Paradox",
                "https://iep.utm.edu/rus-par/": "Russell's Paradox",
                "https://iep.utm.edu/set-theo/": "Set Theory",
                "https://iep.utm.edu/goedel/": "Godel's Incompleteness Theorems",
                "https://iep.utm.edu/comptic/": "Computability",
                "https://iep.utm.edu/argument/": "Argument",
                "https://iep.utm.edu/ded-arg/": "Deductive Arguments",
                "https://iep.utm.edu/ind-arg/": "Inductive Arguments",
                "https://iep.utm.edu/analogy/": "Analogical Arguments",
                "https://iep.utm.edu/def-log/": "Definitions",
                "https://iep.utm.edu/counterfactuals/": "Counterfactuals",
                "https://iep.utm.edu/crit-thi/": "Critical Thinking",
                "https://iep.utm.edu/inf-best/": "Inference to the Best Explanation",
                "https://iep.utm.edu/prob-log/": "Probability and Logic",
                "https://iep.utm.edu/deontic/": "Deontic Logic",
                "https://iep.utm.edu/epist-lo/": "Epistemic Logic",
            },
        },
        "history-of-philosophy": {
            "pages": {
                "https://iep.utm.edu/plato/": "Plato",
                "https://iep.utm.edu/aristotl/": "Aristotle",
                "https://iep.utm.edu/socrates/": "Socrates",
                "https://iep.utm.edu/presocratics/": "Presocratics",
                "https://iep.utm.edu/thales/": "Thales",
                "https://iep.utm.edu/heraclit/": "Heraclitus",
                "https://iep.utm.edu/parmenid/": "Parmenides",
                "https://iep.utm.edu/zeno-par/": "Zeno's Paradoxes",
                "https://iep.utm.edu/empedocl/": "Empedocles",
                "https://iep.utm.edu/democrit/": "Democritus",
                "https://iep.utm.edu/epicurus/": "Epicurus",
                "https://iep.utm.edu/stoicism/": "Stoicism",
                "https://iep.utm.edu/stoiceth/": "Stoic Ethics",
                "https://iep.utm.edu/pyrrhon/": "Pyrrhonian Skepticism",
                "https://iep.utm.edu/plotinus/": "Plotinus",
                "https://iep.utm.edu/augustin/": "Augustine",
                "https://iep.utm.edu/aquinas/": "Thomas Aquinas",
                "https://iep.utm.edu/anselm/": "Anselm",
                "https://iep.utm.edu/ockham/": "William of Ockham",
                "https://iep.utm.edu/machiave/": "Machiavelli",
                "https://iep.utm.edu/hobbes/": "Thomas Hobbes",
                "https://iep.utm.edu/locke/": "John Locke",
                "https://iep.utm.edu/hume/": "David Hume",
                "https://iep.utm.edu/berkeley/": "George Berkeley",
                "https://iep.utm.edu/descarte/": "Rene Descartes",
                "https://iep.utm.edu/spinoza/": "Baruch Spinoza",
                "https://iep.utm.edu/leibniz/": "Gottfried Leibniz",
                "https://iep.utm.edu/kant/": "Immanuel Kant",
                "https://iep.utm.edu/hegel/": "Georg Wilhelm Friedrich Hegel",
                "https://iep.utm.edu/marx/": "Karl Marx",
                "https://iep.utm.edu/nietzsch/": "Friedrich Nietzsche",
                "https://iep.utm.edu/kierkega/": "Soren Kierkegaard",
                "https://iep.utm.edu/schopenh/": "Arthur Schopenhauer",
                "https://iep.utm.edu/milljs/": "John Stuart Mill",
                "https://iep.utm.edu/bentham/": "Jeremy Bentham",
                "https://iep.utm.edu/rousseau/": "Jean-Jacques Rousseau",
                "https://iep.utm.edu/peirce/": "Charles Sanders Peirce",
                "https://iep.utm.edu/james/": "William James",
                "https://iep.utm.edu/dewey/": "John Dewey",
                "https://iep.utm.edu/russell/": "Bertrand Russell",
                "https://iep.utm.edu/wittgens/": "Ludwig Wittgenstein",
                "https://iep.utm.edu/frege/": "Gottlob Frege",
                "https://iep.utm.edu/husserl/": "Edmund Husserl",
                "https://iep.utm.edu/heidegge/": "Martin Heidegger",
                "https://iep.utm.edu/sartre/": "Jean-Paul Sartre",
                "https://iep.utm.edu/beauvoir/": "Simone de Beauvoir",
                "https://iep.utm.edu/foucault/": "Michel Foucault",
                "https://iep.utm.edu/derrida/": "Jacques Derrida",
                "https://iep.utm.edu/rawls/": "John Rawls",
                "https://iep.utm.edu/arendt/": "Hannah Arendt",
            },
        },
        "philosophy-of-mind": {
            "pages": {
                "https://iep.utm.edu/mind/": "Philosophy of Mind",
                "https://iep.utm.edu/consciou/": "Consciousness",
                "https://iep.utm.edu/qualia/": "Qualia",
                "https://iep.utm.edu/intentio/": "Intentionality",
                "https://iep.utm.edu/mental-c/": "Mental Causation",
                "https://iep.utm.edu/functism/": "Functionalism",
                "https://iep.utm.edu/id-theor/": "Identity Theory",
                "https://iep.utm.edu/behavio/": "Behaviorism",
                "https://iep.utm.edu/dualism/": "Dualism",
                "https://iep.utm.edu/elim-mat/": "Eliminative Materialism",
                "https://iep.utm.edu/prop-dua/": "Property Dualism",
                "https://iep.utm.edu/panpsych/": "Panpsychism",
                "https://iep.utm.edu/epiphen/": "Epiphenomenalism",
                "https://iep.utm.edu/chinese/": "Chinese Room Argument",
                "https://iep.utm.edu/zombies/": "Zombies",
                "https://iep.utm.edu/repr-min/": "Mental Representation",
                "https://iep.utm.edu/folk-psy/": "Folk Psychology",
                "https://iep.utm.edu/compmind/": "Computational Theory of Mind",
                "https://iep.utm.edu/connect/": "Connectionism",
                "https://iep.utm.edu/embodied/": "Embodied Cognition",
                "https://iep.utm.edu/ext-mind/": "Extended Mind",
                "https://iep.utm.edu/emotion/": "Emotion",
                "https://iep.utm.edu/imaginat/": "Imagination",
                "https://iep.utm.edu/percept/": "Perception",
                "https://iep.utm.edu/color/": "Color",
                "https://iep.utm.edu/pain/": "Pain",
                "https://iep.utm.edu/desire/": "Desire",
                "https://iep.utm.edu/belief/": "Belief",
                "https://iep.utm.edu/concepts/": "Concepts",
                "https://iep.utm.edu/att-mind/": "Attention",
                "https://iep.utm.edu/ani-cogn/": "Animal Cognition",
                "https://iep.utm.edu/ani-cons/": "Animal Consciousness",
                "https://iep.utm.edu/art-inte/": "Artificial Intelligence",
                "https://iep.utm.edu/lang-tho/": "Language of Thought",
                "https://iep.utm.edu/priv-lan/": "Private Language",
                "https://iep.utm.edu/dreams/": "Dreams",
                "https://iep.utm.edu/unconsc/": "The Unconscious",
                "https://iep.utm.edu/self-con/": "Self-Consciousness",
                "https://iep.utm.edu/ment-ill/": "Mental Illness",
                "https://iep.utm.edu/neuro-ph/": "Neuroscience and Philosophy",
            },
        },
        "philosophy-of-religion": {
            "pages": {
                "https://iep.utm.edu/religion/": "Philosophy of Religion",
                "https://iep.utm.edu/god-exis/": "Existence of God",
                "https://iep.utm.edu/ont-arg/": "Ontological Argument",
                "https://iep.utm.edu/cos-arg/": "Cosmological Argument",
                "https://iep.utm.edu/tel-arg/": "Teleological Argument",
                "https://iep.utm.edu/evil-log/": "Logical Problem of Evil",
                "https://iep.utm.edu/evil-evi/": "Evidential Problem of Evil",
                "https://iep.utm.edu/theodicy/": "Theodicy",
                "https://iep.utm.edu/miracles/": "Miracles",
                "https://iep.utm.edu/faith-re/": "Faith and Reason",
                "https://iep.utm.edu/relig-ep/": "Religious Epistemology",
                "https://iep.utm.edu/relig-ex/": "Religious Experience",
                "https://iep.utm.edu/rel-plur/": "Religious Pluralism",
                "https://iep.utm.edu/rel-lang/": "Religious Language",
                "https://iep.utm.edu/divine-a/": "Divine Attributes",
                "https://iep.utm.edu/omnipote/": "Omnipotence",
                "https://iep.utm.edu/omniscie/": "Omniscience",
                "https://iep.utm.edu/d-simpli/": "Divine Simplicity",
                "https://iep.utm.edu/afterlif/": "Afterlife",
                "https://iep.utm.edu/immortal/": "Immortality",
                "https://iep.utm.edu/soul/": "The Soul",
                "https://iep.utm.edu/mysticism/": "Mysticism",
                "https://iep.utm.edu/atheism/": "Atheism",
                "https://iep.utm.edu/agnosticism/": "Agnosticism",
                "https://iep.utm.edu/fideism/": "Fideism",
                "https://iep.utm.edu/pascal-w/": "Pascal's Wager",
                "https://iep.utm.edu/prayer/": "Prayer",
                "https://iep.utm.edu/rel-sci/": "Religion and Science",
                "https://iep.utm.edu/rel-mora/": "Religion and Morality",
                "https://iep.utm.edu/d-com-th/": "Divine Command Theory",
                "https://iep.utm.edu/natural-theology/": "Natural Theology",
                "https://iep.utm.edu/process-t/": "Process Theology",
                "https://iep.utm.edu/panenthm/": "Panentheism",
                "https://iep.utm.edu/pantheism/": "Pantheism",
                "https://iep.utm.edu/creation/": "Creation and Conservation",
            },
        },
        "political-philosophy": {
            "pages": {
                "https://iep.utm.edu/poltic-am/": "Political Philosophy",
                "https://iep.utm.edu/soc-cont/": "Social Contract Theory",
                "https://iep.utm.edu/democrac/": "Democracy",
                "https://iep.utm.edu/liberali/": "Liberalism",
                "https://iep.utm.edu/libertarianism/": "Libertarianism",
                "https://iep.utm.edu/socialis/": "Socialism",
                "https://iep.utm.edu/con-ism/": "Conservatism",
                "https://iep.utm.edu/anarchis/": "Anarchism",
                "https://iep.utm.edu/communit/": "Communitarianism",
                "https://iep.utm.edu/multicul/": "Multiculturalism",
                "https://iep.utm.edu/fem-poli/": "Feminist Political Philosophy",
                "https://iep.utm.edu/cosmopol/": "Cosmopolitanism",
                "https://iep.utm.edu/national/": "Nationalism",
                "https://iep.utm.edu/colonial/": "Colonialism",
                "https://iep.utm.edu/authority/": "Authority",
                "https://iep.utm.edu/legitima/": "Legitimacy",
                "https://iep.utm.edu/sovereig/": "Sovereignty",
                "https://iep.utm.edu/obligati/": "Political Obligation",
                "https://iep.utm.edu/civil-di/": "Civil Disobedience",
                "https://iep.utm.edu/free-spe/": "Freedom of Speech",
                "https://iep.utm.edu/tolerati/": "Toleration",
                "https://iep.utm.edu/justice/": "Justice",
                "https://iep.utm.edu/dist-jus/": "Distributive Justice",
                "https://iep.utm.edu/equality/": "Equality",
                "https://iep.utm.edu/property/": "Property",
                "https://iep.utm.edu/human-ri/": "Human Rights",
                "https://iep.utm.edu/rep-govt/": "Representative Government",
                "https://iep.utm.edu/pub-reas/": "Public Reason",
                "https://iep.utm.edu/exploit/": "Exploitation",
                "https://iep.utm.edu/revoluti/": "Revolution",
                "https://iep.utm.edu/global-j/": "Global Justice",
                "https://iep.utm.edu/immigrat/": "Immigration",
                "https://iep.utm.edu/aff-acti/": "Affirmative Action",
                "https://iep.utm.edu/reparati/": "Reparations",
                "https://iep.utm.edu/republic/": "Republicanism",
            },
        },
        "aesthetics": {
            "pages": {
                "https://iep.utm.edu/aestheti/": "Aesthetics",
                "https://iep.utm.edu/beauty/": "Beauty",
                "https://iep.utm.edu/aes-judg/": "Aesthetic Judgment",
                "https://iep.utm.edu/art-defi/": "Definition of Art",
                "https://iep.utm.edu/art-expr/": "Artistic Expression",
                "https://iep.utm.edu/fiction/": "Fiction",
                "https://iep.utm.edu/humor/": "Humor",
                "https://iep.utm.edu/sublime/": "The Sublime",
                "https://iep.utm.edu/taste/": "Taste",
                "https://iep.utm.edu/aes-exp/": "Aesthetic Experience",
                "https://iep.utm.edu/env-aest/": "Environmental Aesthetics",
                "https://iep.utm.edu/music-ph/": "Philosophy of Music",
                "https://iep.utm.edu/film-phi/": "Philosophy of Film",
                "https://iep.utm.edu/photo-ae/": "Photography",
                "https://iep.utm.edu/imaginat/": "Imagination",
                "https://iep.utm.edu/creativ/": "Creativity",
                "https://iep.utm.edu/forgery/": "Forgery",
                "https://iep.utm.edu/art-mora/": "Art and Morality",
                "https://iep.utm.edu/art-valu/": "The Value of Art",
                "https://iep.utm.edu/art-onto/": "Ontology of Art",
                "https://iep.utm.edu/tragedy/": "Tragedy",
                "https://iep.utm.edu/narratic/": "Narrative",
                "https://iep.utm.edu/depict/": "Depiction",
                "https://iep.utm.edu/art-crit/": "Art Criticism",
                "https://iep.utm.edu/art-cogn/": "Art and Cognition",
            },
        },
        "ancient": {
            "pages": {
                "https://iep.utm.edu/anc-phil/": "Ancient Philosophy",
                "https://iep.utm.edu/plato-me/": "Plato: Metaphysics",
                "https://iep.utm.edu/plato-et/": "Plato: Ethics",
                "https://iep.utm.edu/plato-ep/": "Plato: Epistemology",
                "https://iep.utm.edu/plat-pol/": "Plato: Political Philosophy",
                "https://iep.utm.edu/plat-rhe/": "Plato: Rhetoric",
                "https://iep.utm.edu/aris-met/": "Aristotle: Metaphysics",
                "https://iep.utm.edu/aris-eth/": "Aristotle: Ethics",
                "https://iep.utm.edu/aris-pol/": "Aristotle: Politics",
                "https://iep.utm.edu/aris-log/": "Aristotle: Logic",
                "https://iep.utm.edu/aris-bio/": "Aristotle: Biology",
                "https://iep.utm.edu/presocra/": "Presocratic Philosophy",
                "https://iep.utm.edu/milesian/": "Milesian School",
                "https://iep.utm.edu/pythagor/": "Pythagoras",
                "https://iep.utm.edu/xenophan/": "Xenophanes",
                "https://iep.utm.edu/anaximen/": "Anaximenes",
                "https://iep.utm.edu/anaximan/": "Anaximander",
                "https://iep.utm.edu/sophists/": "Sophists",
                "https://iep.utm.edu/protagor/": "Protagoras",
                "https://iep.utm.edu/gorgias/": "Gorgias",
                "https://iep.utm.edu/diogenes/": "Diogenes of Sinope",
                "https://iep.utm.edu/cynics/": "Cynics",
                "https://iep.utm.edu/epicurea/": "Epicureanism",
                "https://iep.utm.edu/academic/": "Academic Skepticism",
                "https://iep.utm.edu/neoplato/": "Neoplatonism",
                "https://iep.utm.edu/cicero/": "Cicero",
                "https://iep.utm.edu/lucretiu/": "Lucretius",
                "https://iep.utm.edu/seneca/": "Seneca",
                "https://iep.utm.edu/marcus-a/": "Marcus Aurelius",
                "https://iep.utm.edu/epictetu/": "Epictetus",
            },
        },
        "modern": {
            "pages": {
                "https://iep.utm.edu/mod-phil/": "Modern Philosophy",
                "https://iep.utm.edu/desc-epi/": "Descartes: Epistemology",
                "https://iep.utm.edu/desc-met/": "Descartes: Metaphysics",
                "https://iep.utm.edu/desc-min/": "Descartes: Mind-Body Problem",
                "https://iep.utm.edu/spin-met/": "Spinoza: Metaphysics",
                "https://iep.utm.edu/spin-eth/": "Spinoza: Ethics",
                "https://iep.utm.edu/leib-met/": "Leibniz: Metaphysics",
                "https://iep.utm.edu/leib-min/": "Leibniz: Mind-Body Problem",
                "https://iep.utm.edu/lock-pol/": "Locke: Political Philosophy",
                "https://iep.utm.edu/lock-kno/": "Locke: Knowledge",
                "https://iep.utm.edu/hume-cau/": "Hume: Causation",
                "https://iep.utm.edu/hume-mor/": "Hume: Moral Philosophy",
                "https://iep.utm.edu/hume-rel/": "Hume: Religion",
                "https://iep.utm.edu/berk-epi/": "Berkeley: Epistemology",
                "https://iep.utm.edu/kant-met/": "Kant: Metaphysics",
                "https://iep.utm.edu/kant-eth/": "Kant: Ethics",
                "https://iep.utm.edu/kant-aes/": "Kant: Aesthetics",
                "https://iep.utm.edu/reid/": "Thomas Reid",
                "https://iep.utm.edu/hutcheso/": "Francis Hutcheson",
                "https://iep.utm.edu/smith-mo/": "Adam Smith: Moral Philosophy",
                "https://iep.utm.edu/voltaire/": "Voltaire",
                "https://iep.utm.edu/montesqu/": "Montesquieu",
                "https://iep.utm.edu/condilla/": "Condillac",
                "https://iep.utm.edu/la-mettrie/": "La Mettrie",
                "https://iep.utm.edu/diderot/": "Diderot",
                "https://iep.utm.edu/bacon-fr/": "Francis Bacon",
                "https://iep.utm.edu/galileo/": "Galileo",
                "https://iep.utm.edu/newton/": "Isaac Newton",
                "https://iep.utm.edu/shaftes/": "Shaftesbury",
                "https://iep.utm.edu/wolff/": "Christian Wolff",
            },
        },
        "continental": {
            "pages": {
                "https://iep.utm.edu/cont-phi/": "Continental Philosophy",
                "https://iep.utm.edu/phenom/": "Phenomenology",
                "https://iep.utm.edu/existent/": "Existentialism",
                "https://iep.utm.edu/hermeneu/": "Hermeneutics",
                "https://iep.utm.edu/crit-the/": "Critical Theory",
                "https://iep.utm.edu/structur/": "Structuralism",
                "https://iep.utm.edu/postmode/": "Postmodernism",
                "https://iep.utm.edu/deconstr/": "Deconstruction",
                "https://iep.utm.edu/frankfur/": "Frankfurt School",
                "https://iep.utm.edu/habermas/": "Habermas",
                "https://iep.utm.edu/adorno/": "Adorno",
                "https://iep.utm.edu/benjamin/": "Walter Benjamin",
                "https://iep.utm.edu/marcuse/": "Herbert Marcuse",
                "https://iep.utm.edu/levinas/": "Emmanuel Levinas",
                "https://iep.utm.edu/merleau/": "Merleau-Ponty",
                "https://iep.utm.edu/ricoeur/": "Paul Ricoeur",
                "https://iep.utm.edu/gadamer/": "Hans-Georg Gadamer",
                "https://iep.utm.edu/deleuze/": "Gilles Deleuze",
                "https://iep.utm.edu/baudrillard/": "Jean Baudrillard",
                "https://iep.utm.edu/lyotard/": "Jean-Francois Lyotard",
                "https://iep.utm.edu/irigaray/": "Luce Irigaray",
                "https://iep.utm.edu/kristeva/": "Julia Kristeva",
                "https://iep.utm.edu/butler/": "Judith Butler",
                "https://iep.utm.edu/agamben/": "Giorgio Agamben",
                "https://iep.utm.edu/badiou/": "Alain Badiou",
            },
        },
        "analytic": {
            "pages": {
                "https://iep.utm.edu/analytic/": "Analytic Philosophy",
                "https://iep.utm.edu/log-pos/": "Logical Positivism",
                "https://iep.utm.edu/log-atom/": "Logical Atomism",
                "https://iep.utm.edu/ord-lang/": "Ordinary Language Philosophy",
                "https://iep.utm.edu/vienna/": "Vienna Circle",
                "https://iep.utm.edu/quine/": "W.V.O. Quine",
                "https://iep.utm.edu/kripke/": "Saul Kripke",
                "https://iep.utm.edu/davidson/": "Donald Davidson",
                "https://iep.utm.edu/dummett/": "Michael Dummett",
                "https://iep.utm.edu/putnam/": "Hilary Putnam",
                "https://iep.utm.edu/lewis-dk/": "David Lewis",
                "https://iep.utm.edu/rorty/": "Richard Rorty",
                "https://iep.utm.edu/sellars/": "Wilfrid Sellars",
                "https://iep.utm.edu/strawson/": "P.F. Strawson",
                "https://iep.utm.edu/anscombe/": "G.E.M. Anscombe",
                "https://iep.utm.edu/foot/": "Philippa Foot",
                "https://iep.utm.edu/wil-ber/": "Bernard Williams",
                "https://iep.utm.edu/parfit/": "Derek Parfit",
                "https://iep.utm.edu/nagel/": "Thomas Nagel",
                "https://iep.utm.edu/searle/": "John Searle",
                "https://iep.utm.edu/dennett/": "Daniel Dennett",
                "https://iep.utm.edu/chalmers/": "David Chalmers",
                "https://iep.utm.edu/carnap/": "Rudolf Carnap",
                "https://iep.utm.edu/ayer/": "A.J. Ayer",
                "https://iep.utm.edu/ryle/": "Gilbert Ryle",
            },
        },
        "eastern": {
            "pages": {
                "https://iep.utm.edu/east-phi/": "Eastern Philosophy",
                "https://iep.utm.edu/buddhism/": "Buddhism",
                "https://iep.utm.edu/buddha/": "The Buddha",
                "https://iep.utm.edu/zen/": "Zen Buddhism",
                "https://iep.utm.edu/hinduism/": "Hindu Philosophy",
                "https://iep.utm.edu/vedanta/": "Vedanta",
                "https://iep.utm.edu/yoga/": "Yoga",
                "https://iep.utm.edu/confucius/": "Confucius",
                "https://iep.utm.edu/confucian/": "Confucianism",
                "https://iep.utm.edu/mencius/": "Mencius",
                "https://iep.utm.edu/xunzi/": "Xunzi",
                "https://iep.utm.edu/zhuangzi/": "Zhuangzi",
                "https://iep.utm.edu/laozi/": "Laozi",
                "https://iep.utm.edu/daoism/": "Daoism",
                "https://iep.utm.edu/legalism/": "Chinese Legalism",
                "https://iep.utm.edu/mohism/": "Mohism",
                "https://iep.utm.edu/neo-conf/": "Neo-Confucianism",
                "https://iep.utm.edu/japanese/": "Japanese Philosophy",
                "https://iep.utm.edu/nishida/": "Kitaro Nishida",
                "https://iep.utm.edu/african/": "African Philosophy",
                "https://iep.utm.edu/afric-et/": "African Ethics",
                "https://iep.utm.edu/ubuntu/": "Ubuntu",
                "https://iep.utm.edu/indian-e/": "Indian Ethics",
                "https://iep.utm.edu/jainism/": "Jainism",
                "https://iep.utm.edu/nagarjun/": "Nagarjuna",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"iep-{source_key}" if source_key else "iep"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles, nav, header, footer, sidebar and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' - Internet Encyclopedia of Philosophy',
                           ' | Internet Encyclopedia of Philosophy',
                           ' | IEP']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"iep-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping iep/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    IEPScraper(base, source_key).run()
