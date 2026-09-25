import io,json,zipfile,hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np,trimesh

root=Path(__file__).resolve().parent.parent
models=root/'models'
report={}
s=trimesh.load(models/'model.glb',force='scene')
assert len(s.geometry)==17
report['glb_objects']=len(s.geometry)
source=trimesh.load(root/'reference/preferred.glb',force='scene')
assert np.allclose(s.bounds,source.bounds,atol=1e-6)
report['source_bounds_preserved']=True
unchanged=[0,1,2,3,4,5,6,7,8,10,11,15]
for index in unchanged:
    a=source.geometry[f'model_part{index}']
    b=next(m for n,m in s.geometry.items() if n.startswith(f'{index:02d}-'))
    assert np.array_equal(a.vertices,b.vertices),index
    assert np.array_equal(a.faces,b.faces),index
report['unchanged_parts_exact']=unchanged
with zipfile.ZipFile(models/'ayri-parcalar-150mm-STL.zip') as z:
    assert z.testzip() is None
    files=[n for n in z.namelist() if n.endswith('.stl')]
    assert len(files)==17
    parts=[];bounds=[]
    for name in files:
        m=trimesh.load(io.BytesIO(z.read(name)),file_type='stl',process=True)
        assert np.isfinite(m.vertices).all(),name
        assert m.is_watertight,name
        assert m.is_winding_consistent,name
        bounds.append(m.bounds)
        parts.append({'file':name,'faces':len(m.faces),'watertight':True,'winding_consistent':True})
    b=np.array(bounds);height=float(b[:,1,2].max()-b[:,0,2].min())
    assert abs(height-150)<.001
    report['assembled_height_mm']=height
    report['stl_parts']=parts
with zipfile.ZipFile(models/'parcali-model-150mm.3mf') as z:
    assert z.testzip() is None
    ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    r=ET.fromstring(z.read('3D/3dmodel.model'))
    meshes=r.findall('m:resources/m:object/m:mesh',ns)
    assert len(meshes)==17 and r.attrib['unit']=='millimeter'
    for mesh in meshes:
        n=len(mesh.findall('m:vertices/m:vertex',ns))
        for f in mesh.findall('m:triangles/m:triangle',ns):
            assert all(0<=int(f.attrib[k])<n for k in ('v1','v2','v3'))
    report['three_mf_objects']=len(meshes)
    report['three_mf_indices_valid']=True
surface=json.load(open(root/'reports/surface-comparison.json'))
assert len(surface['views'])==10
assert all(v['lost_silhouette_rays']==0 and v['added_silhouette_rays']==0 for v in surface['views'])
assert all(v['rays_over_0_1mm']==0 for v in surface['views'])
report['exterior_surface_check']={'views':10,'rays':sum(v['rays'] for v in surface['views']),'silhouette_changes':0,'max_difference_mm':max(v['max_surface_difference_mm'] for v in surface['views'])}
report['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in models.iterdir() if p.is_file()}
(root/'reports/export-verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
