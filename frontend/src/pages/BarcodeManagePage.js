import { useState, useEffect, useCallback } from 'react';
import { useAuth, api } from '../contexts/AuthContext';
import { BarcodeDisplay } from '../components/BarcodeDisplay';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { ScanBarcode, Search, Zap, CheckCircle, AlertTriangle, Package } from 'lucide-react';
import { toast } from 'sonner';

export default function BarcodeManagePage() {
  const { currentBranch } = useAuth();
  const [tab, setTab] = useState('no-barcode');
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [genSingle, setGenSingle] = useState(null); // product id being generated

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/products', { params: { limit: 2000, is_repack: false } });
      setProducts(res.data.products || []);
    } catch { toast.error('Failed to load products'); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const noBarcodeProducts = products.filter(p => !p.barcode);
  const hasBarcodeProducts = products.filter(p => p.barcode);

  const filtered = (list) => {
    if (!search.trim()) return list;
    const s = search.toLowerCase();
    return list.filter(p =>
      p.name?.toLowerCase().includes(s) ||
      p.sku?.toLowerCase().includes(s) ||
      p.barcode?.toLowerCase().includes(s)
    );
  };

  const handleBulkGenerate = async () => {
    setGenerating(true);
    try {
      const res = await api.post('/products/generate-barcodes-bulk');
      const count = res.data.generated || 0;
      if (count > 0) {
        toast.success(`Generated barcodes for ${count} product(s)`);
        fetchProducts();
      } else {
        toast.info('All parent products already have barcodes');
      }
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed to generate barcodes'); }
    setGenerating(false);
  };

  const handleSingleGenerate = async (productId) => {
    setGenSingle(productId);
    try {
      const res = await api.post(`/products/${productId}/generate-barcode`);
      toast.success(`Barcode assigned: ${res.data.barcode}`);
      fetchProducts();
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed'); }
    setGenSingle(null);
  };

  return (
    <div className="space-y-6 animate-fadeIn" data-testid="barcode-manage-page">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ fontFamily: 'Manrope' }}>Barcode Management</h1>
          <p className="text-sm text-slate-500 mt-1">
            Generate and manage barcodes for your products
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="outline" className="gap-1 text-amber-600 border-amber-200 bg-amber-50">
              <AlertTriangle size={12} /> {noBarcodeProducts.length} No Barcode
            </Badge>
            <Badge variant="outline" className="gap-1 text-emerald-600 border-emerald-200 bg-emerald-50">
              <CheckCircle size={12} /> {hasBarcodeProducts.length} With Barcode
            </Badge>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <Input
            data-testid="barcode-manage-search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, SKU, or barcode..."
            className="pl-9 h-10"
          />
        </div>
        {noBarcodeProducts.length > 0 && (
          <Button
            onClick={handleBulkGenerate}
            disabled={generating}
            className="bg-[#1A4D2E] hover:bg-[#14532d] text-white"
            data-testid="bulk-generate-btn"
          >
            <Zap size={16} className="mr-2" />
            {generating ? 'Generating...' : `Generate All (${noBarcodeProducts.length})`}
          </Button>
        )}
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="no-barcode" data-testid="tab-no-barcode">
            No Barcode ({noBarcodeProducts.length})
          </TabsTrigger>
          <TabsTrigger value="has-barcode" data-testid="tab-has-barcode">
            With Barcode ({hasBarcodeProducts.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="no-barcode" className="mt-4">
          {filtered(noBarcodeProducts).length > 0 ? (
            <Card className="border-slate-200">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Product</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">SKU</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Category</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Unit</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium w-40 text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered(noBarcodeProducts).map(p => (
                      <TableRow key={p.id}>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell><code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{p.sku}</code></TableCell>
                        <TableCell className="text-slate-600">{p.category}</TableCell>
                        <TableCell className="text-slate-600">{p.unit}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline" size="sm"
                            onClick={() => handleSingleGenerate(p.id)}
                            disabled={genSingle === p.id}
                            data-testid={`gen-barcode-${p.id}`}
                          >
                            <ScanBarcode size={13} className="mr-1.5" />
                            {genSingle === p.id ? 'Generating...' : 'Generate'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed border-slate-300">
              <CardContent className="py-12 text-center">
                <CheckCircle size={40} className="mx-auto text-emerald-300 mb-3" />
                <p className="text-slate-500 font-medium">All products have barcodes!</p>
                <p className="text-sm text-slate-400 mt-1">Every parent product has been assigned a unique barcode</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="has-barcode" className="mt-4">
          {filtered(hasBarcodeProducts).length > 0 ? (
            <Card className="border-slate-200">
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-slate-50">
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Product</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">SKU</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Barcode</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Preview</TableHead>
                      <TableHead className="text-xs uppercase tracking-wider text-slate-500 font-medium">Category</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered(hasBarcodeProducts).map(p => (
                      <TableRow key={p.id}>
                        <TableCell className="font-medium">{p.name}</TableCell>
                        <TableCell><code className="text-xs bg-slate-100 px-1.5 py-0.5 rounded">{p.sku}</code></TableCell>
                        <TableCell>
                          <code className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-mono">{p.barcode}</code>
                        </TableCell>
                        <TableCell>
                          <BarcodeDisplay value={p.barcode} width={0.8} height={24} fontSize={8} />
                        </TableCell>
                        <TableCell className="text-slate-600">{p.category}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed border-slate-300">
              <CardContent className="py-12 text-center">
                <Package size={40} className="mx-auto text-slate-300 mb-3" />
                <p className="text-slate-500 font-medium">No products with barcodes yet</p>
                <p className="text-sm text-slate-400 mt-1">Switch to the "No Barcode" tab and generate barcodes</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
