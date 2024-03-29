#!/usr/bin/env python3

class FileBlockCodes:
    """
    Definitions of codes found in Blender file block headers
    """
    fileBlockCodes = {
        'SC' : 'Scene',
        'LI' :  'Library',
        'OB' :  'Object',
        'ME' :  'Mesh',
        'CU' :  'Curve',
        'MB' :  'MetaBall',
        'MA' :  'Material',
        'TE' :  'Tex (Texture)',
        'IM' :  'Image',
        'LT' :  'Lattice',
        'LA' :  'Light',
        'CA' :  'Camera',
        'IP' :  'Ipo (depreciated, replaced by FCurves)',
        'KE' :  'Key (shape key)',
        'WO' :  'World',
        'SR' : 'Screen',
        'VF' :  'VFont (Vector Font)',
        'TX' : 'Text',
        'SK' : 'Speaker',
        'SO' :  'Sound',
        'GR' :  'Group',
        'AR' :  'bArmature',
        'AC' :  'bAction',
        'NT' :  'bNodeTree',
        'BR' :  'Brush',
        'PA' :  'ParticleSettings',
        'GD' :  'bGPdata, (Grease Pencil)',
        'WM' :  'WindowManager',
        'MC' :  'MovieClip',
        'MS' : 'Mask',
        'LS' :  'FreestyleLineStyle',
        'PL' : 'Palette',
        'PC' :  'PaintCurve ',
        'CF' :  'CacheFile',
        'WS' :  'WorkSpace',
        'LP' :  'LightProbe',
        # typically owned by #ID's, will be freed when there are no users
        'DATA' :  'Arbitrary allocated memory',
        'GLOB' : 'Used for #Global struct',
        'DNA1' : 'Used for storing the encoded SDNA string',
        'TEST' : 'Used to store thumbnail previews',
        # can be easily read by other applications without writing a full blend file parser
        'REND' : 'Used for #RenderInfo, basic Scene and frame range info',
        'USER' : 'Used for #UserDef, (user-preferences data)',
        'ENDB' : 'Terminate reading (no data)',
        'SN' : 'Screen (deprecated)',
    }
