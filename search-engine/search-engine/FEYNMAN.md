# Feynman Explains: IR Models for a 12-Year-Old

Ten sections. Each uses a library or school-fair analogy to explain one idea
behind this search engine in plain language.

## 1. Information Retrieval and the Library

Imagine a giant library with a million books. You walk in with a question:
"best treatment for diabetes." You cannot read every book, so you need a system
that finds the right few books fast and puts the best one on top. That system is
called Information Retrieval, or IR for short. A search engine is just a very
fast librarian. The librarian takes your words, looks them up in a special
catalog, decides which books match, and then ranks them so the most useful one
is first. The catch is that "useful" is fuzzy. Two books may both contain the
word diabetes, but one is a recipe blog and the other is a medical study. Good
IR tries to guess which one you actually want, using clues like how rare each
word is and where it appears. Throughout these notes we will pretend the
computer is a librarian at a school book fair, and every idea is a trick the
librarian uses to serve you faster and more accurately.

## 2. Tokenization and Stop-Words

Before the librarian can help, she must chop your question into pieces. The
sentence "The running machines" becomes the tokens "the", "running",
"machines". Chopping text into clean word-pieces is called tokenization. But
some words are useless for searching. "The" appears in almost every book, so it
tells the librarian nothing. We drop these common filler words, called
stop-words: the, is, of, a, and, and so on. After this step, "The running
machines" leaves just "running" and "machines." Think of it like a school-fair
ticket booth where the teacher crosses out the boring words on your slip and
keeps only the meaningful ones. Tokenization and stop-word removal shrink the
question down to the words that actually carry meaning. This makes every later
step faster and more accurate, because the librarian stops wasting effort on
words that show up everywhere and cannot tell two books apart. The same
cleaning happens to the books too, so questions and books speak the same
trimmed language.

## 3. Stemming

Now the librarian notices a problem: "running", "runs", and "ran" are really
the same idea, but they look different to a computer. If a book says "machine"
and you ask for "machines", a naive search would miss it. Stemming fixes this by
trimming the ends of words so they shrink to a common root. "running" becomes
"run", and "machines" becomes "machin". It is like cutting the crusts off
sandwiches at the school fair so two sandwiches with different crusts but the
same filling count as the same snack. Our project uses a Porter-style stemmer, a
set of rules invented in 1980 that chops suffixes in a careful order. It is not
perfect: "compute" and "computing" can end up different. But it is good enough
that a search for "treatment" finds documents about "treatments" too, which is
what makes matching reliable across many word forms without keeping a giant
dictionary of every variant the language can produce.

## 4. The Inverted Index (Card Catalog)

A normal list of books goes book -> words. But a librarian searching fast wants
the opposite: word -> books. That reverse list is the inverted index. For every
word, it stores the list of books that contain it and how many times. So the
entry for "diabet" might say: books 11, 12, 13. This is exactly like a library
card catalog: one card per topic, listing the shelf numbers of every book on
that topic. When you ask a question, the librarian does not open all the books.
She pulls the cards for your words and looks at which books appear on several
cards. Our index is even smarter: it remembers positions of words, so we can
tell whether words sit close together, and it keeps separate cards for each part
of a document, like title, abstract, and method. Those extra cards let us
search by field later, which matters when a word in the title is far more
meaningful than the same word buried deep in the body text.

## 5. Boolean Retrieval (AND, OR, NOT)

Sometimes you want exact control. "Give me books with diabetes AND treatment"
means a book must have both words. "diabetes OR exercise" means either word is
fine. "NOT fiction" rules out novels. This is Boolean retrieval, named after the
mathematician George Boole. It is like a strict gatekeeper at the school fair:
you may enter only if you carry a ticket with the right stamps. The gatekeeper
does not rank people, only lets them in or keeps them out, so every admitted
book gets the same score of 1. Our parser even understands parentheses, so
"(diabetes OR glucose) AND treatment" means: first allow books with either
diabetes or glucose, then keep only those that also have treatment. Boolean is
great for precision when you know exactly what you want, and it is blindingly
fast because it just intersects lists. But it never tells you which matching
book is best, which is why we need the ranking models that come next.

## 6. Vector Space Model (Arrows and Cosine)

To rank books, the librarian turns each one into an arrow, where every word is a
direction and the weight of the word is how far the arrow points that way. Your
question becomes an arrow too. Books that point in a similar direction talk
about similar things. The angle between the question-arrow and a book-arrow
measures similarity: a small angle means a strong match. We use the cosine of
that angle, which is 1 when arrows overlap perfectly and 0 when they are
perpendicular, meaning no shared words. In the lecture example, the query
"retrieval ranking" sits closest to a document about "retrieval indexing
ranking" with cosine 0.816, and has nothing in common with "database
normalization" at 0.0. This is the Vector Space Model: ranking by the angle
between word-arrows. It is elegant because a short query and a long book live in
the same space and can be compared directly, and the cosine naturally favours
books that share your rare, meaningful words.

## 7. TF-IDF (Rare Words Matter More)

Not every matching word is equally important. If a word appears in almost every
book, it is not very informative. If a word appears in only one or two books, it
is a strong signal. TF-IDF captures this with two ideas multiplied together. TF
(term frequency) is how often a word appears in a book. IDF (inverse document
frequency) is how rare the word is across the whole library. Multiply them and
rare-but-present words get big weights while common words shrink. Imagine the
school-fair raffle: a word printed on every ticket is worth almost nothing, but
a word printed on only three tickets is a valuable clue for finding those
three. In our diabetes query, "diabet" appears in just three documents, so it
gets a high IDF and pulls the right books to the top. TF-IDF is the weight used
inside the Vector Space Model's arrows, so a book that shares rare words with
your question naturally points in a similar direction and ranks higher.

## 8. BM25 (Smart Saturation and Length)

BM25 is the grown-up version of TF-IDF and the ranker used by Lucene and
Elasticsearch. It adds two clever ideas. First, term frequency saturates:
mentioning a word twice is better than once, but the tenth mention adds almost
nothing, so a book cannot win just by repeating a word. A knob called k1
controls this flattening. Second, it normalises document length: a long book
naturally has more words, so BM25 scales by length using a knob called b,
stopping thick books from dominating. Think of a fair judge who knows that a kid
who shouts "diabetes" ten times is not ten times more relevant than one who says
it once, and who discounts entries from kids who wrote giant posters. The
formula sums a tuned score per query term, and it consistently beats plain
TF-IDF on retrieval benchmarks, which is why BM25 is the default ranker in this
project and the safe first choice for any keyword search system.

## 9. BIM and Probability of Relevance

The Binary Independence Model asks a different question: what is the
probability that a book is relevant, given the words in my query? It guesses
using the Robertson-Sparck Jones weight, which compares how often a word shows
up in relevant books versus non-relevant ones. With no prior information this
reduces to "rare words are evidence of relevance." The model is binary: a word
is either present or not, so it ignores how many times it appears. The neat
trick is relevance feedback: once you mark a few books as useful, the librarian
updates the weights, called R and r, so the next search is sharper. Our code
even maps the score through a sigmoid to turn it into a clean probability
between 0 and 1, which is easy to read and compare. BIM is the theoretical
ancestor of BM25, and it shines when you can gather relevance judgements over
time, like a librarian who slowly learns your taste and gets better with every
visit.

## 10. Evaluation: Precision, Recall, MRR

How do we know the librarian is any good? We test her. Pick a question, decide
the truly correct books in advance, and check what she returns. Precision asks:
of the books she showed, how many were actually right? Recall asks: of all the
right books that exist, how many did she find? A perfect librarian scores 1.0 on
both. MRR (mean reciprocal rank) cares about how quickly the first good book
appears: finding it on the first result scores 1, on the second scores 1/2, and
so on. We also use nDCG and average precision for a fuller picture. In our
tests, BM25, the Vector Space Model, and field-weighted BM25 all hit recall of
1.0 and MRR of 1.0 on the diabetes query, while the unranked Boolean model lags
on precision because it cannot order its matches. Evaluation is the scorecard
that turns opinions into numbers and lets us compare models honestly and
repeatably.
