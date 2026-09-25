import json, pathlib, zipfile, trimesh, numpy as np
from xml.sax.saxutils import escape

root=pathlib.Path(__file__).resolve().parent.parent
out=root/'models'
s=trimesh.load(out/'model.glb',force='scene')
parts=[]
for i,node in enumerate(s.graph.nodes_geometry,1):
    transform,key=s.graph[node]
    m=s.geometry[key].copy(); m.apply_transform(transform)
    parts.append((str(node),str(node),m))
bounds=np.array([m.bounds for _,_,m in parts])
lo=bounds[:,0,:].min(axis=0); hi=bounds[:,1,:].max(axis=0)
scale=150.0/(hi[1]-lo[1])
matrix=np.array([[scale,0,0,-(hi[0]+lo[0])/2*scale],
                 [0,0,-scale,(hi[2]+lo[2])/2*scale],
                 [0,scale,0,-lo[1]*scale],[0,0,0,1]])
manifest=[]
for label,node,m in parts:
    m.apply_transform(matrix)
    manifest.append(dict(file=label+'.stl',source_object=node,triangles=len(m.faces),
        watertight=m.is_watertight,dimensions_mm=m.extents.tolist()))
with zipfile.ZipFile(out/'ayri-parcalar-150mm-STL.zip','w',zipfile.ZIP_DEFLATED) as z:
    for label,node,m in parts: z.writestr(label+'.stl',m.export(file_type='stl'))
    z.writestr('parca-listesi.json',json.dumps(manifest,indent=2))
    z.writestr('OKU.txt','Birim: mm. Montaj halinde toplam yukseklik: 150 mm. Her STL ayri bir Meshy nesnesidir. Dosyalar ortak montaj koordinatlarini korur. STL dokulari ve renkleri tasimaz. Otomatik pim eklenmemistir. Dilimleyicide tum dosyalari tek bir cok-parcali nesne olarak iceri aktarin veya tek tek tablaya yerlestirin.\n')
with zipfile.ZipFile(out/'parcali-model-150mm.3mf','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>')
    z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with z.open('3D/3dmodel.model','w') as f:
        def write(x): f.write(x.encode())
        write('<?xml version="1.0" encoding="UTF-8"?><model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"><resources>')
        for i,(label,node,m) in enumerate(parts,1):
            write(f'<object id="{i}" type="model" name="{escape(label)}"><mesh><vertices>')
            for chunk in np.array_split(m.vertices,max(1,len(m.vertices)//10000)):
                write(''.join(f'<vertex x="{x:.9g}" y="{y:.9g}" z="{zz:.9g}"/>' for x,y,zz in chunk))
            write('</vertices><triangles>')
            for chunk in np.array_split(m.faces,max(1,len(m.faces)//10000)):
                write(''.join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a,b,c in chunk))
            write('</triangles></mesh></object>')
        assembly=len(parts)+1
        write(f'<object id="{assembly}" type="model" name="Assembled figure 150mm"><components>')
        for i in range(1,len(parts)+1): write(f'<component objectid="{i}"/>')
        write(f'</components></object></resources><build><item objectid="{assembly}"/></build></model>')
(out/'parca-listesi.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(dict(parts=len(parts),height_mm=150,scale=scale,manifest=manifest),indent=2))
