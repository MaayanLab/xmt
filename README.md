# "X" Matrix Transpose (XMT)

This format is a variation on the Gene Matrix Transpose (GMT) serialization format for gene set libraries. The serialization format is effectively a sparse matrix serialization.

This library provides a helper for parsing GMTs (.gmt) AND XMTs (.xmt)

In addition to the sparse matrix serialization, XMT extends the format with optional "frontmatter" (in the same way markdown frontmatter works). This frontmatter contains versioned yaml metadata helping to describe what the XMT contains.

## Example XMT

```example/simple.gmt
---
# the xmt file format version
version: "1.0"
# a description of what the terms/set label represent
term: "anatomy"
# a description of what the entities represent, preferrably a well known IRI which could be prefixed to find the entity
#  e.g. {this_field}:{the_actual_entity} so hgnc.symbol:ACE2 which can be resolved with https://identifiers.org/hgnc.symbol:ACE2
entity: "hgnc.symbol"
# if `true` the ordering of the entities in the row is from most significant to least significant
ordered: false
# a template that can be used to construct a human readable assertion about
#  the relationship between the term and the entity being captured in this XMT
# NOTE: {entity} and {term} are used literally, not as a substitution
label: "{entity} is upregulated in {term}"
# a link to a repository/source/description of how this was generated
source: "https://github.com/… or https://doi.org/…"

# all lines after the close fence (---) are of the form:
# term	description	list of entities separated by tabs
---
adipose (UBERON:0001013)		FAH	LIFR	H2AFJ	NAGLU	ACE2
whole blood (UBERON:0001012)		FAH	LIFR	STAT2	STAT3
```
