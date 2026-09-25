from pathlib import Path
import trimesh,numpy as np,json,io
R=Path(__file__).resolve().parent.parent
s=trimesh.load(R/'models/model.glb',force='scene')
reports=[]
lo,hi=s.bounds;scale=150/(hi[1]-lo[1])
center=np.array([(lo[0]+hi[0])/2,lo[1],(lo[2]+hi[2])/2])
def mm_mesh(m):
    m=m.copy();v=(m.vertices-center)*scale
    m.vertices=np.column_stack([v[:,0],-v[:,2],v[:,1]])
    return m
for name,m in list(s.geometry.items()):
    if int(name[:2]) not in [9,12,13,14,16]:continue
    before=m.vertices.copy();rng=np.random.default_rng(100+int(name[:2]))
    perturbed=set()
    for attempt in range(5):
        trial=mm_mesh(m)
        # STL stores float32 coordinates. Keep topologically distinct vertices
        # distinct at that precision without deleting faces or components.
        coords=trial.vertices.astype(np.float32)
        _,inverse,count=np.unique(coords,axis=0,return_inverse=True,return_counts=True)
        bad=np.flatnonzero(count[inverse]>1)
        if len(bad):
            normals=rng.normal(size=(len(bad),3));normals/=np.linalg.norm(normals,axis=1)[:,None]
            m.vertices[bad]+=normals*(1e-5*(attempt+1))
            perturbed.update(bad.tolist())
        check=trimesh.load(io.BytesIO(mm_mesh(m).export(file_type='stl')),file_type='stl',process=True)
        print(name,'attempt',attempt,'coincident vertices',len(bad),'STL watertight',check.is_watertight,flush=True)
        if check.is_watertight and check.is_winding_consistent:break
    assert check.is_watertight and check.is_winding_consistent,name
    reports.append({'name':name,'faces_retained':len(m.faces),'vertices_regularized':len(perturbed),'max_vertex_displacement_mm':float(np.linalg.norm(m.vertices-before,axis=1).max()*scale),'stl_reload_watertight':True,'stl_reload_winding_consistent':True,'method':'Separate coincident topologically distinct vertices at STL coordinate precision; deterministic bounded perturbation, no faces or components removed.'})
s.export(R/'models/model.glb')
json.dump(reports,open(R/'reports/mesh-cleanup.json','w'),indent=2)
