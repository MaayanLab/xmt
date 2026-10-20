import xmt
import sys
import click
import pathlib
from ruamel.yaml import YAML

@click.group()
def cli(): pass

@cli.command()
@click.option('-i', '--input', type=click.Path(file_okay=True, exists=True, allow_dash=True), default='-')
@click.option('--input-format', type=click.Choice(['xmt', 'tsv', 'yaml']), default=None)
@click.option('-o', '--output', type=click.Path(file_okay=True, allow_dash=True), default='-')
@click.option('--output-format', type=click.Choice(['xmt', 'tsv', 'yaml', 'json']), default=None)
def convert(input, input_format: str, output: click.Path, output_format: str):
  if not input_format and input != '-':
    input = pathlib.Path(input)
    if input.suffix in {'.txt', '.xmt', '.gmt', '.dmt'}: input_format = 'xmt'
    elif input.suffix in {'.tsv'}: input_format = 'tsv'
    elif input.suffix in {'.json', '.yml', '.yaml'}: input_format = 'yaml'
    else: raise RuntimeError('Unknown input format please specify')
  if not output_format and output != '-':
    output = pathlib.Path(output)
    if output.suffix in {'.xmt', '.gmt', '.dmt'}: output_format = 'xmt'
    elif output.suffix in {'.tsv'}: output_format = 'tsv'
    elif output.suffix in {'.yml', '.yaml'}: output_format = 'yaml'
    elif output.suffix in {'.json'}: output_format = 'json'
    else: raise RuntimeError('Unknown output format please specify')
  if input_format != 'xmt' and output_format is None: output_format = 'xmt'
  if input_format is None and output_format != 'xmt': input_format = 'xmt'
  assert input_format and output_format
  #
  if input_format == 'xmt':
    data = xmt.from_file(sys.stdin if input == '-' else input)
  elif input_format == 'tsv':
    import pandas as pd
    data = xmt.from_pandas(pd.read_csv(sep='\t', index_col=0))
  elif input_format == 'yaml':
    yaml = YAML()
    with pathlib.Path(input).open('r') as fr:
      data = xmt.from_dict(yaml.load(fr), with_description=False)
  else:
    raise NotImplementedError(input_format)
  #
  if output_format == 'xmt':
    data.to_file(sys.stdout if output == '-' else output)
  elif output_format == 'tsv':
    data.to_pandas().to_csv(sys.stdout if output == '-' else output, sep='\t')
  elif output_format == 'yaml':
    yaml = YAML()
    with pathlib.Path('/dev/stdout' if output == '-' else output).open('w') as fw:
      yaml.dump(data.to_dict(with_description=False), fw)
  elif output_format == 'json':
    import json
    with pathlib.Path('/dev/stdout' if output == '-' else output).open('w') as fw:
      json.dump(data.to_dict(with_description=False), fw)
  else:
    raise NotImplementedError(output_format)

if __name__ == '__main__':
  cli()
