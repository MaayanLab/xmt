import re
import io
import abc
import typing
import pathlib
import logging
import itertools
import functools
from dataclasses import dataclass

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)

class _PeekableFile(io.TextIOBase):
  def __init__(self, fp):
    self.fp = fp
    self.peeked = []
  def seekable(self):
    return self.fp.seekable()
  def seek(self, pos, whence = 0):
    self.peeked = []
    return self.fp.seek(pos, whence)
  def tell(self):
    if self.peeked: return self.peeked[0][0]
    else: return self.fp.tell()
  def __iter__(self): return self
  def __next__(self):
    if self.peeked:
      _pos, line = self.peeked.pop(0)
    else:
      line = self.fp.readline()
      if not line: raise StopIteration
    return line
  def peek(self):
    pos, line = (self.tell(), self.fp.readline())
    self.peeked.append((pos, line))
    return line

class _OneShotIterable:
  def __init__(self, it):
    self.it = it
    self.consumed = False
  def __call__(self):
    return self
  def __iter__(self):
    return self
  def __next__(self):
    if self.consumed: raise RuntimeError('Iterable was already consumed')
    try:
      return next(self.it)
    except StopIteration:
      self.consumed = True
      raise

class Frontmatter(typing.TypedDict):
	# the xmt file format version
  version: str = '1.0'
	# a description of what the terms/set label represent
  term: str = ''
	# compact IRI prefix to combine with the entities/set elements
  entity: str = ''
	# if `true` the ordering of the entities in the row is from most significant to least significant
  ordered: bool = False
  # {entity} and {term} as a literal template, not as a substitution, e.g. {entity} is upregulated in {term}
  label: str = '{entity} has some relationship to {term}'
	# a link to a repository/source/description of how this was generated
  source: str = ''

  
def read_v0(file: io.TextIOBase) -> typing.Iterable[typing.Tuple[str, str, list[str]]]:
  ''' Read XMT v0 (i.e. GMT/DMT without frontmatter)
  '''
  pos = file.tell() if file.seekable() else None
  for i, line in enumerate(map(str.strip, file)):
    if not line: continue
    line_split = line.split('\t')
    if len(line_split) < 3:
      logger.warning('Ignoring line {} with no entities'.format(i))
      continue
    term, description, *entity_list = line_split
    # TODO: deal with oddly formatted entities
    yield term, description, entity_list
  if pos is not None: file.seek(pos)

def from_iter(iterable: typing.Iterable[typing.Tuple[str, str, list[str]]]):
  return LazyXMT(xmt_iter=_OneShotIterable(iterable))

def from_dict(d, with_descriptions=True):
  if with_descriptions:
    return LazyXMT(xmt_iter=lambda d=d: ((term, desc, entity_list) for (term, desc), entity_list in d.items()))
  else:
    return LazyXMT(xmt_iter=lambda d=d: ((term, '', entity_list) for term, entity_list in d.items()))

def from_file(file: typing.Union[io.TextIOBase, str, pathlib.Path]):
  if isinstance(file, str): file = pathlib.Path(file)
  if isinstance(file, pathlib.Path): file = file.open('r')
  if not isinstance(file, io.TextIOBase): raise NotImplementedError(f"{type(file)=}")
  #
  file = _PeekableFile(file)
  line0 = file.peek().strip()
  if line0 != '---':
    logger.warning('Expected fence, got none, file is not formatted as XMT, assuming GMT/DMT')
    frontmatter = Frontmatter(version='0.0')
  else:
    next(file)
    frontmatter_raw = []
    for line in map(str.strip, file):
      if line == '---': break
      frontmatter_raw.append(line)
    assert line == '---', 'Expected close fence, got none'
    frontmatter = YAML().load('\n'.join(frontmatter_raw))
  #
  return LazyXMT(
    frontmatter=frontmatter,
    xmt_iter=functools.partial(read_v0, file),
  )

class XMT(abc.ABC):
  @property
  @abc.abstractmethod
  def frontmatter(self) -> Frontmatter: pass
  @property
  @abc.abstractmethod
  def background(self) -> list[str]: pass
  @property
  @abc.abstractmethod
  def terms(self) -> typing.Iterable[str]: pass
  @property
  @abc.abstractmethod
  def descriptions(self) -> typing.Iterable[str]: pass
  @property
  @abc.abstractmethod
  def entity_lists(self) -> typing.Iterable[list[str]]: pass
  @abc.abstractmethod
  def __iter__(self) -> typing.Iterator[typing.Tuple[str, str, list[str]]]: pass
  @abc.abstractmethod
  def __len__(self) -> int: pass
  @property
  def shape(self):
    return len(self), len(self.background)
  @abc.abstractmethod
  def concat(self, *xmts) -> 'XMT': pass
  @abc.abstractmethod
  def append(self, term: str, description: str, entity_list: list[str]) -> 'XMT': pass

  def to_file(self, file: typing.Union[str, pathlib.Path, io.TextIOBase], mode: str = 'w'):
    close = False
    if isinstance(file, str): file = pathlib.Path(file)
    if isinstance(file, pathlib.Path):
      file = file.open(mode)
      close = True
    yaml = YAML()
    if mode != 'a' and self.frontmatter != '0.0':
      print('---', file=file)
      yaml.dump(self.frontmatter, file)
      print('---', file=file)
    for term, description, entity_list in self:
      print(term, description, *entity_list, sep='\t', file=file)
    if close:
      file.close()

  def to_string(self):
    with io.StringIO() as fp:
      self.to_file(fp)
      return fp.getvalue()

  def to_dict(self, with_description=True):
    return {
      (term, description): entity_list
      for term, description, entity_list in self
    } if with_description else {
      term: entity_list
      for term, _description, entity_list in self
    }

  def to_spmatrix(self):
    ''' create a sparse matrix from this GMT
    '''
    import scipy.sparse
    import numpy as np
    gene_index = { gene: index for index, gene in enumerate(self.background) }
    spmatrix = scipy.sparse.dok_matrix((len(self), len(gene_index)), dtype=np.int8)
    for i, entity_list in enumerate(self.entity_lists):
      spmatrix[i, [gene_index[g] for g in entity_list]] = 1
    return spmatrix

  def to_pandas(self):
    ''' create a sparse pandas dataframe from this GMT
    '''
    import pandas as pd
    return pd.DataFrame.sparse.from_spmatrix(
      self.to_spmatrix(),
      columns=self.background,
      index=self.terms,
    )

  def transpose(self):
    xmt_T = {}
    for term, _description, entity_list in self:
      for entity in entity_list:
        if entity not in xmt_T: xmt_T[entity] = []
        xmt_T[entity].append(term)
    xmt = from_dict(xmt_T, with_descriptions=False)
    xmt.frontmatter = Frontmatter(
      entity=self.frontmatter['term'],
      term=self.frontmatter['entity'],
      source=self.frontmatter['source'],
      ordered=False,
      label=self.frontmatter['label'].replace('{term}', '{tmp}').replace('{entity}', '{term}').replace('{tmp}', '{entity}'),
    )
    return xmt

class LazyXMT(XMT):
  def __init__(self, frontmatter: typing.Optional[Frontmatter] = None, xmt_iter: typing.Optional[typing.Callable[[], typing.Iterator[typing.Tuple[str, str, list[str]]]]] = None):
    super().__init__()
    self._frontmatter = Frontmatter() if frontmatter is None else frontmatter
    self._xmt_iter = (lambda: tuple()) if xmt_iter is None else xmt_iter

  @property
  def frontmatter(self):
    return self._frontmatter

  @frontmatter.setter
  def frontmatter(self, value):
    self._frontmatter = value

  def __iter__(self):
    return self._xmt_iter()

  @property
  def background(self):
    background = {}
    for _term, _description, entity_list in self:
      background.update(dict.fromkeys(entity_list))
    return list(background)

  @property
  def terms(self):
    terms = []
    for term, _description, _entity_list in self:
      terms.append(term)
    return terms

  @property
  def descriptions(self):
    descriptions = []
    for _term, description, _entity_list in self:
      descriptions.append(description)
    return descriptions

  @property
  def entity_lists(self):
    entity_lists = []
    for _term, _description, entity_list in self:
      entity_lists.append(entity_list)
    return entity_lists

  def __len__(self):
    return sum(1 for _ in self)

  def concat(self, *xmts):
    self._xmt_iter = _OneShotIterable(itertools.chain(self, *xmts))
    return self

  def append(self, term: str, description: str, entity_list: list[str]):
    self._xmt_iter = _OneShotIterable(itertools.chain(self, (term, description, entity_list)))
    return self

  def to_dense(self):
    xmt = DenseXMT(frontmatter=self._frontmatter)
    for term, description, entity_list in self:
      xmt.append(term, description, entity_list)
    return xmt

class DenseXMT(XMT):
  @property
  def frontmatter(self): return self._frontmatter
  @frontmatter.setter
  def frontmatter(self, value):
    self._frontmatter = value
  @property
  def background(self): return self._background
  @property
  def terms(self): return self._terms
  @property
  def descriptions(self): return self._descriptions
  @property
  def entity_lists(self): return self._entity_lists

  def __iter__(self):
    return zip(self.terms, self.descriptions, self.entity_lists)

  def __len__(self):
    return len(self._terms)

  def __init__(self, frontmatter: typing.Optional[Frontmatter] = None, background: typing.Optional[list[str]] = None, terms: typing.Optional[list[str]] = None, descriptions: typing.Optional[list[str]] = None, entity_lists: typing.Optional[list[list[str]]] = None):
    super().__init__()
    self._frontmatter = Frontmatter() if frontmatter is None else frontmatter
    self._background = [] if background is None else background
    self._terms = [] if terms is None else terms
    self._descriptions = [] if descriptions is None else descriptions
    self._entity_lists = [] if entity_lists is None else entity_lists

  def concat(self, *xmts):
    for xmt in xmts:
      if isinstance(xmt, DenseXMT):
        self._background = list(dict.fromkeys(self._background + xmt.background))
        self._terms += xmt.terms
        self._descriptions += xmt.descriptions
        self._entity_lists += xmt.entity_lists
      else:
        for term, description, entity_list in xmt:
          self.append(term, description, entity_list)
    return self
  
  def append(self, term: str, description: str, entity_list: list[str]):
    self._background = list(dict.fromkeys(self._background + entity_list))
    self._terms.append(term)
    self._descriptions.append(description)
    self._entity_lists.append(entity_list)
    return self
