// MeshCooker.cpp : cook an OBJ into Madness engine-compliant mesh chunks

#define PX_PHYSX_STATIC_LIB
#ifdef _WIN64
#pragma comment(lib, "C:\\PhysX3.3.4\\Lib\\vc14win64\\PhysX3DEBUG_x64.lib")
#pragma comment(lib, "C:\\PhysX3.3.4\\Lib\\vc14win64\\PhysX3CommonDEBUG_x64.lib")
#pragma comment(lib, "C:\\PhysX3.3.4\\Lib\\vc14win64\\PhysX3CookingDEBUG_x64.lib")
#pragma comment(lib, "C:\\PhysX3.3.4\\Lib\\vc14win64\\PhysX3ExtensionsDEBUG.lib")
#pragma comment(lib, "C:\\PhysX3.3.4\\Lib\\vc14win64\\PhysXProfileSDKDEBUG.lib")
#else // 32-bit build
#pragma comment(lib, "PhysX3.lib")
#pragma comment(lib, "PhysX3Common.lib")
#pragma comment(lib, "PhysX3Cooking.lib")
#pragma comment(lib, "PhysX3Extensions.lib")
#pragma comment(lib, "PhysXProfileSDK.lib")
#endif

#include <PxPhysicsAPI.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>
#include <string>
#include <cstdint>
#include <windows.h> // CreateDirectory
#include <unordered_map>
#include <algorithm>

using namespace physx;

// very small OBJ loader (vertices + faces only, groups become sub-meshes)
struct RawMesh
{
    std::vector<PxVec3> verts;
    std::vector<PxU32> indices; // always 32-bit in memory
    void clear()
    {
        verts.clear();
        indices.clear();
    }
};

//  OBJ loader that preserves groups / objects
struct ObjGroup
{
    std::string name;
    std::vector<PxU32> indices; // indices into the *global* vert list
};

static bool loadOBJGroups(const char *path, std::vector<PxVec3> &verts, std::vector<ObjGroup> &groups, bool fixRotation)
{
    std::ifstream in(path);
    if (!in)
    {
        std::cerr << "Cannot open " << path << "\n";
        return false;
    }

    auto newGroup = [&](const std::string &n)
    {
        groups.push_back({n, {}}); // create empty group
    };
    newGroup("default");

    std::string line;
    while (std::getline(in, line))
    {
        if (line.empty() || line[0] == '#')
            continue;
        std::istringstream ss(line);

        if (line.rfind("v ", 0) == 0) // vertex
        {
            char c;
            double x, y, z;
            ss >> c >> x >> y >> z;
            if (fixRotation)
                z = -z;
            verts.emplace_back(static_cast<float>(x), static_cast<float>(y), static_cast<float>(z));
        }
        else if (line.rfind("f ", 0) == 0) // polygon – triangulate
        {
            char c;
            ss >> c;
            std::vector<std::string> toks;
            std::string t;
            while (ss >> t)
                toks.push_back(t);
            if (toks.size() < 3)
                continue;

            auto idxOf = [&](const std::string &tok) -> PxU32
            {
                size_t slash = tok.find('/');
                return PxU32(std::stoi(tok.substr(0, slash)) - 1);
            };
            for (size_t i = 1; i + 1 < toks.size(); ++i)
            {
                PxU32 tri[3] = {idxOf(toks[0]), idxOf(toks[i]), idxOf(toks[i + 1])};
                if (fixRotation)
                    std::swap(tri[1], tri[2]);
                groups.back().indices.insert(groups.back().indices.end(), tri, tri + 3);
            }
        }
        else if (line.rfind("o ", 0) == 0 || line.rfind("g ", 0) == 0) // new group
        {
            char c;
            std::string name;
            ss >> c >> name;
            if (groups.back().indices.empty())
                groups.back().name = name; // rename default if still unused
            else
                newGroup(name);
        }
    }
    if (!groups.empty() && groups.back().indices.empty())
        groups.pop_back();

    size_t triTotal = 0;
    for (auto &g : groups)
        triTotal += g.indices.size() / 3;
    std::cout << "OBJ: " << verts.size() << " verts, " << triTotal << " tris in " << groups.size() << " groups\n";
    return !verts.empty() && !groups.empty();
}

// helper: write cooked bytes out file, optionally append
static bool dump(const std::string &path, const std::vector<uint8_t> &data, bool append)
{
    std::ofstream f(path, append ? std::ios::binary | std::ios::app : std::ios::binary);
    if (!f)
    {
        std::cerr << "Cannot open " << path << " for write\n";
        return false;
    }
    f.write((const char *)data.data(), data.size());
    return true;
}

// ----------------------------------------------------------------------------
//  Terrain Material Lookup Table
// ----------------------------------------------------------------------------
struct MaterialMapping
{
    std::string name;
    uint32_t index;
};

// Material lookup table based on terrainpool_materials.txt
// Ordered by length (longest first) to avoid false matches
static const std::vector<MaterialMapping> TERRAIN_MATERIALS = {
    {"PAINTCRETE_ILLEGAL", 49}, {"PCRETE_ILLEGAL", 49}, {"RDGREEN", 49},
    {"PAINTCRETE_LEGAL", 48}, {"PCRETE_LEGAL", 48},
    {"BUMPYDIRT_ROAD", 20}, {"BDIRT_ROAD", 20},
    {"ILLEGAL_STRIP", 47}, {"ILLEGALSTRIP", 47},
    {"TRAIN_TRACKS", 36}, {"TRAINROAD", 36},
    {"BUMPYCOBBLES", 37}, {"RAMP_METAL", 37},
    {"BUMPYROADS1", 2}, {"B1ROAD", 2},
    {"BUMPYROADS2", 3}, {"B2ROAD", 3}, {"CONC", 3},
    {"BUMPYROADS3", 4}, {"B3ROAD", 4},
    {"BUMPYGRAVEL", 9}, {"BGRV", 9},
    {"BUMPYSAND", 16}, {"BSAND", 16},
    {"BUMPYDIRT", 18}, {"BDIRT", 18},
    {"GRASSYBERMS", 6}, {"GBRM", 6},
    {"LOWGRIPROADS", 1}, {"LGROAD", 1},
    {"RUMBLESTRIPS", 10}, {"BRICK", 10}, {"RMBL", 10},
    {"CEMENTWALLS", 13}, {"CEMA", 13}, {"CWAL", 13}, {"CMWL", 13},
    {"TIREWALLS", 12}, {"TWALL", 12},
    {"GUARDRAILS", 14}, {"GRDR", 14},
    {"DIRT_ROAD", 19},
    {"DIRT BANK", 22}, {"DBANK", 22},
    {"DRY VERGE", 24}, {"DVERGE", 24},
    {"EXITRUMBLES", 25}, {"ERUMBLE", 25}, {"RMBBL", 25},
    {"GRASSCRETE", 26}, {"GCRETE", 26},
    {"LONGGRASS", 27}, {"LNGGRS", 27},
    {"SLOPEGRASS", 28}, {"SLPGRS", 28},
    {"SAND_ROAD", 30}, {"SNDROAD", 30},
    {"BAKED_CLAY", 31}, {"BAKEDCLAY", 31},
    {"ASTROTURF", 32}, {"ASTRO", 32},
    {"DAMAGEDROAD1", 35}, {"DAMROAD1", 35},
    {"B1RUMBLES", 40}, {"B1RUMBLE", 40},
    {"B2RUMBLES", 41}, {"B2RUMBLE", 41},
    {"ROUGHSAND1", 42}, {"RSAND1", 42},
    {"ROUGHSAND2", 43}, {"RSAND2", 43},
    {"SNOWWALLS", 44}, {"SWALLS", 44},
    {"ORION_ONLY", 39}, {"ORIONONLY", 39},
    {"SNOWHALF", 33}, {"SNOW", 33},
    {"RALLY_TARMAC", 51},
    {"RALLYTARMAC", 50},
    {"RUNOFFROAD", 46},
    {"SNOWFULL", 34},
    {"WOODRAILS", 23}, {"WDRL", 23},
    {"PAVEMENT", 21},
    {"ICEROAD", 45},
    {"COBBLES", 29},
    {"RMPMTL", 38}, {"RAMP", 38},
    {"ROADS", 0}, {"ROAD", 0},
    {"MARBLES", 5},
    {"GRASS", 7}, {"GRAS", 7}, {"LOGO", 7}, {"FLDGRASS", 7}, {"RDGRASS", 7},
    {"GRAVEL", 8}, {"GRV", 8}, {"GRAV", 8}, {"GBER", 8},
    {"DRAINS", 11}, {"DRAIN", 11},
    {"SAND", 15}, {"SBER", 15},
    {"DIRT", 17}
};

// Function to get material index from object name
static uint32_t getMaterialIndex(const std::string &objectName)
{
    // Convert to uppercase for case-insensitive matching
    std::string upperName = objectName;
    std::transform(upperName.begin(), upperName.end(), upperName.begin(), ::toupper);

    // Check for prefix matches (ordered by length, longest first)
    for (const auto &material : TERRAIN_MATERIALS)
    {
        if (upperName.find(material.name) == 0)
        { // Check if name starts with material name
            return material.index;
        }
    }

    // Default to ROADS (index 0) if no match found
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 3)
    {
        std::cout << "Usage: PhysicsMeshCooker <in.obj> <out.csm>\n";
        return 1;
    }
    const char *objPath = argv[1];
    const char *outPath = argv[2];

    std::cout << "Loading OBJ file: " << objPath << std::endl;

    std::vector<PxVec3> globalVerts;
    std::vector<ObjGroup> groups;
    if (!loadOBJGroups(objPath, globalVerts, groups, /*mirrorX*/ true))
    {
        std::cerr << "Failed to load OBJ file: " << objPath << std::endl;
        return 1;
    }

    /* ------------------------------------------------------------------ */
    /*  PhysX initialisation (foundation, physics, cooking)               */
    /* ------------------------------------------------------------------ */
    std::cout << "Initializing PhysX..." << std::endl;

    static PxDefaultErrorCallback gErrorCallback;
    static PxDefaultAllocator gAllocator;
    PxFoundation *foundation = PxCreateFoundation(PX_PHYSICS_VERSION, gAllocator, gErrorCallback);
    if (!foundation)
    {
        std::cerr << "Failed to create PhysX foundation" << std::endl;
        return 1;
    }

    PxTolerancesScale scale;
    PxPhysics *physics = PxCreatePhysics(PX_PHYSICS_VERSION, *foundation, scale);
    if (!physics)
    {
        std::cerr << "Failed to create PhysX physics" << std::endl;
        foundation->release();
        return 1;
    }

    // Use parameters that preserve maximum mesh fidelity
    PxCookingParams params(scale);
    params.meshPreprocessParams = PxMeshPreprocessingFlags(0);
    params.targetPlatform = PxPlatform::ePC;
    params.suppressTriangleMeshRemapTable = false;
    PxCooking *cooking = PxCreateCooking(PX_PHYSICS_VERSION, *foundation, params);
    if (!cooking)
    {
        std::cerr << "Failed to create PhysX cooking" << std::endl;
        physics->release();
        foundation->release();
        return 1;
    }

    std::cout << "PhysX initialized successfully" << std::endl;

    /* ------------------------------------------------------------------ */
    /*  Build & cook one mesh per OBJ group                               */
    /* ------------------------------------------------------------------ */
    std::vector<std::vector<uint8_t>> chunks; // Store all chunks before writing
    size_t grpId = 0;

    for (const auto &grp : groups)
    {
        if (grp.indices.empty())
        {
            ++grpId;
            continue;
        }

        // ----- compact vertices for this group -------------------------
        RawMesh raw;
        std::vector<PxU32> remap(globalVerts.size(), UINT32_MAX);

        // Preserve all vertices
        bool preserveAllVertices = true;
        if (preserveAllVertices)
        {
            // Include all vertices from the group's vertex range
            raw.verts = globalVerts;
            for (PxU32 gi : grp.indices)
            {
                raw.indices.push_back(gi);
            }
        }
        else
        {
            // Original compaction logic
            for (PxU32 gi : grp.indices)
            {
                PxU32 li = remap[gi];
                if (li == UINT32_MAX)
                {
                    li = PxU32(raw.verts.size());
                    remap[gi] = li;
                    raw.verts.push_back(globalVerts[gi]);
                }
                raw.indices.push_back(li);
            }
        }

        size_t triangleCount = raw.indices.size() / 3;

        // Describe the mesh
        PxTriangleMeshDesc desc;
        desc.points.count = PxU32(raw.verts.size());
        desc.points.stride = sizeof(PxVec3);
        desc.points.data = raw.verts.data();
        desc.triangles.count = PxU32(triangleCount);
        desc.triangles.stride = 3 * sizeof(PxU32);
        desc.triangles.data = raw.indices.data();
        desc.flags = PxMeshFlags(); // 32-bit indices

        PxDefaultMemoryOutputStream cooked;
        if (!cooking->cookTriangleMesh(desc, cooked))
        {
            std::cerr << "PhysX cook failed for group " << grpId << " (" << grp.name << ")\n";
            return 1;
        }

        // Validate that cooking preserved vertex and triangle counts
        std::cout << "  Input: " << desc.points.count << " vertices, " << desc.triangles.count << " triangles\n";
        std::cout << "  Cooked size: " << cooked.getSize() << " bytes\n";

        // Get material index from group name
        uint32_t materialIndex = getMaterialIndex(grp.name);

        // Build chunk: [size:4][mesh_data][material_index:4]
        uint32_t meshSize = cooked.getSize();

        std::vector<uint8_t> chunk;
        chunk.reserve(4 + meshSize + 4);

        // Write mesh size
        chunk.insert(chunk.end(), reinterpret_cast<const uint8_t *>(&meshSize), reinterpret_cast<const uint8_t *>(&meshSize) + 4);

        // Write mesh data
        chunk.insert(chunk.end(), cooked.getData(), cooked.getData() + cooked.getSize());

        // Write material index
        chunk.insert(chunk.end(), reinterpret_cast<const uint8_t *>(&materialIndex), reinterpret_cast<const uint8_t *>(&materialIndex) + 4);

        chunks.push_back(std::move(chunk));

        std::cout << "  cooked group " << grpId << " (" << grp.name << ") : " << raw.verts.size() << " verts, " << desc.triangles.count << " tris, material: " << materialIndex << "\n";
        ++grpId;
    }

    // Write the complete CSM file: [version:4][chunk1][chunk2]...
    uint32_t chunkCount = static_cast<uint32_t>(chunks.size());
    const uint32_t csmVersion = 330;

    // Write version
    std::vector<uint8_t> header(4);
    std::memcpy(header.data(), &csmVersion, 4);
    if (!dump(outPath, header, /*append*/ false))
        return 1;

    // Write all chunks
    for (const auto &chunk : chunks)
    {
        if (!dump(outPath, chunk, /*append*/ true))
            return 1;
    }

    /* ------------------------------------------------------------------ */
    /*  tidy up                                                           */
    /* ------------------------------------------------------------------ */
    cooking->release();
    physics->release();
    foundation->release();

    std::cout << "Wrote " << outPath << " with " << chunkCount << " chunks\n";
    return 0;
}