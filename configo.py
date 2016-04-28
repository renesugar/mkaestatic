import argparse
import yaml

from os import path

from mdsplit import mdsplit

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')

    args = parser.parse_args()
    input_fn = args.input

    input_fn_base, _ = path.splitext( input_fn )
    output_cfg_fn = input_fn_base + ".yml"

    with open(args.input, 'r') as md_file:
        md_source = md_file.read()

    cfg_src, _ =    mdsplit(md_source)
    config =        yaml.load(cfg_src)
    config_yaml =   yaml.dump(config)

    if path.exists( output_cfg_fn ):
        with open(output_cfg_fn, 'r') as yml_file_ro:
            if yml_file_ro.read() != config_yaml:
                overwrite = True
            else:
                overwrite = False
    else:
        overwrite = True

    if overwrite:
        with open(output_cfg_fn, 'w') as yml_file:
            yml_file.write(config_yaml)

if __name__ == "__main__":
    main()

