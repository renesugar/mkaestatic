
# This python program is part of the mkaestatic program/
# script collection. mkaestatic can be used for static 
# website generation. 
#
# statico.py is the 'heart' of mkaestatic as it implements 
# the rendering of pages using the jinja template engine 
# and the mistune markdown implementation. 
# 
# statico.py also generates dependency files for each markdown 
# source file which add the respective static dependencies of the 
# page to the makefile dependency tree. 
#
# Author: Michael Borinsky
# Github: https://github.com/michibo/mkaestatic
# License: MIT
# Copyright 2016

import argparse

from codecs import open

import os
from os import path

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

import yaml, jinja2, mistune

from mdsplit import mdsplit
from dirlisttree import dirlisttree

def load_configs( config_fns, input_cfg_fn, input_root ):
    ''' This function loads the configuration files 
        of all pages which are part of the project. 

        From the configuration files a 'dirlisttree' instance 
        is generated which mimics the directory structure 
        of the project and which can be accessed conveniently 
        in a jinja template.
    '''
    cfg_tree = dirlisttree()

    for cfg_fn in config_fns:
        if path.isabs(cfg_fn):
            raise ValueError('Error: You cannot use absolute paths here: %s' % cfg_fn)

        cfg_fn_base, _ = path.splitext( cfg_fn )
        _, cfg_name = path.split(cfg_fn_base)
        html_fn = "/" + cfg_fn_base + ".html"

        with open(cfg_fn, 'r', encoding='utf-8') as cfg_file:
            cfg = yaml.load(cfg_file.read())

        # Add special attributes:
        cfg['url'] = html_fn
        cfg['name'] = cfg_name

        if 'title' not in cfg:
            cfg['title'] = cfg_name

        # Configuration of current page gets special attention:
        if cfg_fn == input_cfg_fn:
            config = cfg

        pure_fn, _ = path.split( cfg_fn )

        cfg_tree[pure_fn].append(cfg)

    return cfg_tree, config

def get_url_transform( input_root, soft_dep ):
    ''' This meta function returns a url transformation 
        function which maps absolute urls to relative urls.
    '''

    def url_transform( url ):
        res = urlparse( url )

        # Do nothing if url points to the www
        if res.netloc:
            return url

        if res.path.startswith('/'):
            url = res.path.lstrip('/')
            soft_dep.append(url)
            url = path.relpath( url, input_root )
        else:
            soft_dep.append(path.join(input_root, res.path))
        
        return url

    return url_transform

def load_template( template_fn, hard_dep, url_transform ): 
    ''' This function loads a template and adds the 'localurl' 
        filter to the template environment. More over the 
        custom loader makes sure that all loaded templates are 
        'hard' dependencies.
    '''

    class MyTemplateLoader(jinja2.FileSystemLoader):
        def __init__(self, path):
            self.path = path
            
            super(MyTemplateLoader, self).__init__(path)

        def get_source(self, environment, template):
            tpl_fn = path.join(self.path, template)
            hard_dep.append(tpl_fn)

            return super(MyTemplateLoader, self).get_source(environment, template)
    
    tpl_path, tpl_fname = path.split(template_fn)

    env = jinja2.Environment( loader=MyTemplateLoader(tpl_path or './') )
    env.filters['localurl'] = url_transform 

    return env.get_template(tpl_fname)

def get_markdown_renderer( url_transform ):
    ''' This function returns a markdown renderer which transforms 
        URLs according to the relative paradigm of mkaestatic.
    '''

    class MyRenderer( mistune.Renderer ):
        def link(self, link, title, text):
            link = url_transform(link)
            return super(MyRenderer, self).link(link, title, text)

        def image(self, src, title, alt_text):
            src = url_transform(src)
            return super(MyRenderer, self).image(src, title, alt_text)

    return mistune.Markdown(renderer=MyRenderer(escape=True, use_xhtml=True))

def render( md_source, template_fn, site_cfg, config, cfg_tree, input_root ):
    ''' This function renders the markdown source to html code. 
        
        Moreover, it keeps track of the 'hard' and 'soft' dependencies 
        which are encountered. Hard are dependencies which are necessary 
        to render the html page properly. Soft are dependencies which are 
        necessary to view the page properly in a browser. 

        E.g. the template(s) of the page are hard and the included css 
        files of the page are soft dependencies. 
    '''

    hard_dependencies = []
    soft_dependencies = []

    url_transform = get_url_transform( input_root, soft_dependencies )
    template = load_template( template_fn, hard_dependencies, url_transform )

    markdown = get_markdown_renderer( url_transform )

    content = markdown(md_source)

    way_home = path.relpath( os.curdir, input_root )

    try:
        html_code = template.render( content=content, site=site_cfg, page=config, root=cfg_tree, home=way_home )
    except jinja2.TemplateNotFound as e:
        html_code = "Template not found: %s" % str(e)

    return html_code, soft_dependencies, hard_dependencies

def write_dep_file(output_fn, input_dep_fn, soft_dependencies, hard_dependencies):
    ''' This function writes the .d file.
    '''

    mk_src = "%s %s : %s\nREQUISITES+=%s\n" % ( output_fn, input_dep_fn, " ".join(hard_dependencies), " ".join(soft_dependencies) )
    
    with open(input_dep_fn, 'w', encoding='utf-8') as dep_file:
        dep_file.write(mk_src)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input')
    parser.add_argument('--configs', type=str)
    parser.add_argument('--site_config', type=str)
    
    args = parser.parse_args()
    input_fn = args.input

    input_fn_base, _ = path.splitext( input_fn )
    output_html_fn = input_fn_base + ".html"
    input_cfg_fn = input_fn_base + ".yml"
    input_dep_fn = input_fn_base + ".d"

    input_root, _ = path.split( input_fn_base )

    with open(args.site_config, 'r', encoding='utf-8') as site_cfg_file:
        site_cfg = yaml.load(site_cfg_file.read())

    cfg_fns = args.configs.strip().split(' ')

    cfg_tree, config = load_configs( cfg_fns, input_cfg_fn, input_root )

    if 'mirror' in config:
        # Special mirror keyword:
        mirror_fn = config['mirror']
        
        try:
            with open(mirror_fn, 'r', encoding='utf-8') as mirror_file:
                rendered_source= mirror_file.read()
        except FileNotFound as e:
            rendered_source= "Mirror file not found: %s" % str(e)

        soft_dependencies = []
        hard_dependencies = [mirror_fn]
    else:
        # Render page normaly from source:
        if 'template' in config:
            template_fn = config['template']
        elif 'template' in site_cfg:
            template_fn = site_cfg['template']
        else:
            raise ValueError("No template set in config of %s or in Site.yml" % input_fn)

        with open(input_fn, 'r', encoding='utf-8') as md_file:
            md_source = md_file.read()

        _, md_source = mdsplit(md_source)

        rendered_source, soft_dependencies, hard_dependencies = render(md_source, template_fn, site_cfg, config, cfg_tree, input_root)

    with open(output_html_fn, 'w', encoding='utf-8') as html_file:
        html_file.write(rendered_source)

    write_dep_file(output_html_fn, input_dep_fn, soft_dependencies, hard_dependencies)
    
if __name__ == "__main__":
    main()

