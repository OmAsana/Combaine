package worker

import (
	"fmt"
	"math/rand"
	"time"

	"golang.org/x/net/context"

	"github.com/cocaine/cocaine-framework-go/cocaine"
	"github.com/combaine/combaine/common"
)

// Resolver resolves worker by name
type Resolver interface {
	Resolve(ctx context.Context, name string, hosts []string) (Worker, error)
}

type resolverV11 struct{}

func (r resolverV11) Resolve(ctx context.Context, name string, hosts []string) (Worker, error) {
	for {
		host := fmt.Sprintf("%s:10053", getRandomHost(name, hosts))
		select {
		case r := <-resolve(name, host):
			err, app := r.Err, r.App
			if err == nil {
				return &workerV11{app}, nil
			}
			time.Sleep(50 * time.Millisecond)
		case <-time.After(1 * time.Second):
			// pass
		case <-ctx.Done():
			return nil, common.ErrAppUnavailable
		}
	}
}

// NewResolverV11 returns Resolver for Cocaine V11
func NewResolverV11() Resolver {
	return resolverV11{}
}

func getRandomHost(app string, input []string) string {
	max := len(input)
	return input[rand.Intn(max)]
}

type resolveInfo struct {
	App *cocaine.Service
	Err error
}

func resolve(appname, endpoint string) <-chan resolveInfo {
	res := make(chan resolveInfo)
	go func() {
		app, err := cocaine.NewService(appname, endpoint)
		select {
		case res <- resolveInfo{
			App: app,
			Err: err,
		}:
		default:
			if err == nil {
				app.Close()
			}
		}
	}()
	return res
}
